"""Advanced CampusResOS workflows: recurring bookings, timetable and OS concepts."""
from datetime import date, time, timedelta, datetime
from flask import Blueprint, jsonify, request, session
from db import get_connection
from os_client import worker_command
bp=Blueprint('advanced', __name__)
def admin(): return session.get('role')=='ADMIN'
def fail(msg,code=400): return jsonify({'error':msg}),code
def iso(v): return str(v) if v is not None else None
@bp.post('/api/recurring-bookings/preview')
def recurring_preview():
 if not session.get('user_id'): return fail('Please log in first.',401)
 p=request.get_json(silent=True) or {}
 try:
  room=int(p['classroom_id']); start_date=date.fromisoformat(p['start_date']); weeks=int(p['weeks']); st=time.fromisoformat(p['start_time']); en=time.fromisoformat(p['end_time']); purpose=str(p['purpose']).strip()
 except Exception: return fail('Provide room, start date, number of weeks, times and purpose.')
 if weeks<1 or weeks>26 or st>=en or start_date<date.today() or not purpose: return fail('Use a future start date, 1-26 weeks and a valid time range.')
 dates=[start_date+timedelta(days=7*i) for i in range(weeks)]; conn=get_connection(); cur=conn.cursor(dictionary=True); results=[]
 try:
  cur.execute('SELECT capacity FROM classrooms WHERE classroom_id=%s AND is_active=1',(room,))
  if not cur.fetchone(): return fail('Room is unavailable or inactive.',404)
  for d in dates:
   cur.execute("SELECT booking_id FROM bookings WHERE classroom_id=%s AND booking_date=%s AND status='CONFIRMED' AND start_time<%s AND end_time>%s LIMIT 1",(room,d,en,st)); conflict=cur.fetchone()
   if not conflict:
    cur.execute("SELECT e.timetable_entry_id FROM timetable_entries e JOIN timetables t ON t.timetable_id=e.timetable_id JOIN time_slots s ON s.time_slot_id=e.time_slot_id WHERE e.classroom_id=%s AND e.day_of_week=DAYOFWEEK(%s) AND t.status='PUBLISHED' AND s.start_time<%s AND s.end_time>%s LIMIT 1",(room,d,en,st)); conflict=cur.fetchone()
   results.append({'date':d.isoformat(),'available':not bool(conflict),'reason':None if not conflict else 'Conflicts with a confirmed booking or published timetable'})
  return jsonify({'dates':results,'available_count':sum(x['available'] for x in results),'conflict_count':sum(not x['available'] for x in results),'needs_confirmation':True})
 finally: cur.close(); conn.close()
@bp.post('/api/recurring-bookings/confirm')
def recurring_confirm():
 if not session.get('user_id'): return fail('Please log in first.',401)
 p=request.get_json(silent=True) or {}; dates=p.get('dates'); allow_gaps=p.get('allow_gaps') is True
 if not isinstance(dates,list) or not dates or len(dates)>26: return fail('Preview the recurring booking first.')
 try:
  room=int(p['classroom_id']); st=time.fromisoformat(p['start_time']); en=time.fromisoformat(p['end_time']); purpose=str(p['purpose']).strip(); ds=[date.fromisoformat(x) for x in dates]
 except Exception: return fail('Invalid booking details.')
 if st>=en or len(set(ds))!=len(ds): return fail('Invalid time range or duplicate dates.')
 conn=get_connection(); cur=conn.cursor(dictionary=True); locks=[]; booked=[]; conflicts=[]
 try:
  for d in sorted(ds):
   name=f'cr:{room}:{d.isoformat()}'; cur.execute('SELECT GET_LOCK(%s,5) AS acquired',(name,))
   if (cur.fetchone() or {}).get('acquired')!=1: raise RuntimeError('A room is busy. Please retry.')
   locks.append(name)
  conn.start_transaction()
  cur.execute('SELECT classroom_id FROM classrooms WHERE classroom_id=%s AND is_active=1 FOR UPDATE',(room,))
  if not cur.fetchone(): conn.rollback(); return fail('Room unavailable.',404)
  for d in ds:
   cur.execute("SELECT booking_id FROM bookings WHERE classroom_id=%s AND booking_date=%s AND status='CONFIRMED' AND start_time<%s AND end_time>%s LIMIT 1 FOR UPDATE",(room,d,en,st)); c=cur.fetchone()
   if not c:
    cur.execute("SELECT e.timetable_entry_id FROM timetable_entries e JOIN timetables t ON t.timetable_id=e.timetable_id JOIN time_slots s ON s.time_slot_id=e.time_slot_id WHERE e.classroom_id=%s AND e.day_of_week=DAYOFWEEK(%s) AND t.status='PUBLISHED' AND s.start_time<%s AND s.end_time>%s LIMIT 1",(room,d,en,st)); c=cur.fetchone()
   (conflicts if c else booked).append(d)
  if conflicts and not allow_gaps:
   conn.rollback(); return jsonify({'ok':False,'requires_gap_decision':True,'conflicts':[d.isoformat() for d in conflicts],'available':[d.isoformat() for d in booked],'message':'Some dates conflict. Confirm whether to book only available dates.'}),409
  if not booked: conn.rollback(); return fail('No requested dates are available.',409)
  # Each occurrence is committed in one transaction after the explicit faculty decision.
  for d in booked:
   cur.execute("INSERT INTO bookings(requester_user_id,classroom_id,booking_date,start_time,end_time,purpose,status) VALUES(%s,%s,%s,%s,%s,%s,'CONFIRMED')",(session['user_id'],room,d,st,en,purpose)); bid=cur.lastrowid
   cur.execute("INSERT INTO booking_history(booking_id,actor_user_id,action,details) VALUES(%s,%s,'RECURRING_BOOKING_CONFIRMED',JSON_OBJECT('purpose',%s,'date',%s))",(bid,session['user_id'],purpose,d.isoformat())); booked[-1] if False else None
  conn.commit(); return jsonify({'ok':True,'booked_dates':[d.isoformat() for d in booked],'conflicting_dates':[d.isoformat() for d in conflicts],'booked_count':len(booked),'status':'CONFIRMED'}),201
 except Exception as e:
  conn.rollback(); return fail(str(e),409)
 finally:
  for name in reversed(locks):
   try: cur.execute('SELECT RELEASE_LOCK(%s)',(name,)); cur.fetchone()
   except Exception: pass
  cur.close(); conn.close()
@bp.get('/api/admin/analytics')
def analytics():
 if not session.get('user_id'): return fail('Please log in first.',401)
 if not admin(): return fail('Admin access required.',403)
 conn=get_connection(); cur=conn.cursor(dictionary=True)
 try:
  cur.execute('SELECT * FROM v_room_utilization ORDER BY confirmed_bookings DESC'); rooms=cur.fetchall()
  cur.execute("SELECT status,COUNT(*) AS count FROM bookings GROUP BY status"); statuses=cur.fetchall()
  cur.execute('SELECT COUNT(*) AS total, AVG(waiting_ms) AS avg_wait_ms, AVG(turnaround_ms) AS avg_turnaround_ms FROM os_job_metrics'); metrics=cur.fetchone()
  return jsonify({'rooms':rooms,'booking_statuses':statuses,'os_metrics':metrics})
 finally: cur.close(); conn.close()
@bp.post('/api/os/deadlock-demo')
def deadlock_demo():
 if not session.get('user_id'): return fail('Please log in first.',401)
 # Safe educational graph simulation. Never deliberately deadlocks live booking resources.
 graph={'P1':['R2'],'P2':['R1'],'R1':['P1'],'R2':['P2']}; visiting=set(); visited=set(); cycle=[]
 def dfs(node,path):
  if node in path: cycle.extend(path[path.index(node):]+[node]); return True
  if node in visited: return False
  for nxt in graph.get(node,[]):
   if dfs(nxt,path+[node]): return True
  visited.add(node); return False
 detected=dfs('P1',[])
 conn=get_connection(); cur=conn.cursor()
 try:
  cur.execute('INSERT INTO deadlock_demo_runs(scenario_name,detected,resolution,details) VALUES(%s,%s,%s,JSON_OBJECT(%s,%s))',('two-process-cycle',bool(detected),'Prevent circular wait by ordering resources','cycle',','.join(cycle)))
  conn.commit()
 finally: cur.close(); conn.close()
 return jsonify({'detected':bool(detected),'cycle':cycle,'resolution':'Acquire resources in a global order; cancel/retry one simulated request.','note':'Educational simulation only; live booking service was not deadlocked.'})
@bp.get('/api/os/queue-policy')
def queue_policy():
 if not session.get('user_id'): return fail('Please log in first.',401)
 return jsonify({'policy':'PRIORITY with FCFS tie-breaking','priority_order':{'placement meeting':1,'pre-placement talks':1,'syllabus completion':2,'additional lecture':3,'workshop / seminar':3,'faculty meeting':3,'club events':4,'others':5},'aging':'Increase effective priority for long-waiting jobs','note':'Scheduling demo is educational; final room integrity is enforced by MySQL transactions and room/date locks.'})
