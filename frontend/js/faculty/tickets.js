// Faculty timetable-change ticket submission and ticket list.
async function loadScheduleChangeFormOptions() {
  if (!$("scheduleEntrySelect")) return;
  try {
    const data = await api("/api/faculty/my-schedule");
    const entries = data.regular_entries || data.entries || [];
    $("scheduleEntrySelect").innerHTML = `<option value="">Choose a regular class</option>` + entries.map(entry => {
      const entryId = entry.entry_id ?? entry.timetable_entry_id;
      return `<option value="${Number(entryId)}" data-day="${escapeHtml(entry.day_of_week || "")}" data-slot="${Number(entry.slot_id || 0)}">${escapeHtml(entry.day_of_week || "Day")} · ${escapeHtml(entry.slot_label || entry.activity_name || "Regular class")} · ${escapeHtml(entry.room_code || "")}</option>`;
    }).join("");
    const slots = data.slots || [];
    $("requestedSlot").innerHTML = `<option value="">Choose a slot</option>` + slots.map(slot =>
      `<option value="${Number(slot.slot_id)}">${escapeHtml(slot.slot_label || `${prettyTime(slot.start_time)}–${prettyTime(slot.end_time)}`)}</option>`
    ).join("");
    const rooms = await api("/api/rooms");
    $("requestedClassroom").innerHTML = `<option value="">No classroom change requested</option>` + (rooms.rooms || []).map(room =>
      `<option value="${Number(room.classroom_id)}">${escapeHtml(room.room_code)} · ${escapeHtml(room.room_name || "")}</option>`
    ).join("");
  } catch (error) {
    message("scheduleChangeMessage", `Could not load your timetable options: ${error.message}`, "error");
    $("scheduleEntrySelect").innerHTML = `<option value="">Schedule could not be loaded</option>`;
  }
}
async function loadFacultyTickets() {
  if (!$("facultyTicketRows")) return;
  try {
    const data = await api("/api/faculty/schedule-change-requests");
    const tickets = data.requests || data.tickets || [];
    $("facultyTicketRows").innerHTML = tickets.map(ticket => `
      <tr><td>#${escapeHtml(ticket.ticket_id ?? ticket.request_id)}</td>
      <td>${escapeHtml(ticket.current_day || "—")} ${escapeHtml(ticket.current_slot_label || ticket.current_slot_id || "")}</td>
      <td>${escapeHtml(ticket.requested_day || "—")} ${escapeHtml(ticket.requested_slot_label || ticket.requested_slot_id || "")}</td>
      <td>${escapeHtml(ticket.reason || "")}</td>
      <td>
        <span class="pill status-${String(ticket.status || "PENDING").toLowerCase()}">
          ${escapeHtml(ticket.status || "PENDING")}
        </span>
      </td>
      <td>${escapeHtml(ticket.review_note || ticket.admin_note || "—")}</td></tr>
    `).join("") || `<tr><td colspan="6">You have not raised any timetable tickets.</td></tr>`;
    if ($("facultyTicketMetric")) $("facultyTicketMetric").textContent = tickets.filter(t => String(t.status).toUpperCase() === "PENDING").length;
  } catch (error) {
    $("facultyTicketRows").innerHTML = `<tr><td colspan="6">Tickets could not be loaded.</td></tr>`;
  }
}

$("scheduleChangeForm")?.addEventListener("submit", async event => {
  event.preventDefault();
  const button = event.submitter;
  if (button) button.disabled = true;
  const entry = $("scheduleEntrySelect").selectedOptions[0];
  const payload = {
    timetable_entry_id: Number($("scheduleEntrySelect").value),
    requested_day: $("requestedDay").value,
    requested_slot_id: Number($("requestedSlot").value),
    requested_classroom_id: $("requestedClassroom").value ? Number($("requestedClassroom").value) : null,
    reason: $("scheduleChangeReason").value.trim()
  };
  if (!payload.timetable_entry_id || !payload.requested_day || !payload.requested_slot_id || !payload.reason) {
    message("scheduleChangeMessage", "Please complete all required fields.", "error");
    if (button) button.disabled = false;
    return;
  }
  try {
    await api("/api/faculty/schedule-change-requests", {method:"POST", body:JSON.stringify(payload)});
    message("scheduleChangeMessage", "Ticket submitted. It is now in the admin review queue.");
    $("scheduleChangeForm").reset();
    await loadFacultyTickets();
  } catch (error) {
    message("scheduleChangeMessage", error.message, "error");
  } finally {
    if (button) button.disabled = false;
  }
});

// -------------------- ADMIN ROOM SCHEDULE + UTILIZATION --------------------
