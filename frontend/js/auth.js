// Authentication, session restoration, room/booking/health loaders, and dashboard initialization.
async function loadRooms() {
  const data = await api("/api/rooms");
  const rooms = data.rooms || [];

  if ($("roomCount")) {
    $("roomCount").textContent = rooms.length;
  }

  if ($("facultyRoomMetric")) {
    $("facultyRoomMetric").textContent = rooms.length;
  }

  if ($("adminRoomMetric")) {
    $("adminRoomMetric").textContent = rooms.length;
  }

  // Supports the old booking form if it is still present.
  if ($("classroom")) {
    $("classroom").innerHTML = data.rooms.map((room) => `
      <option value="${room.classroom_id}">
        ${escapeHtml(room.room_code)} ·
        ${escapeHtml(room.room_name)} ·
        Capacity ${escapeHtml(room.capacity)}
      </option>
    `).join("");
  }
}

async function loadBookings() {
  const data = await api("/api/bookings");
  const bookings = data.bookings || [];
  const rows = bookings.map((booking) => `
    <tr>
      <td>#${escapeHtml(booking.booking_id)}</td>
      <td>${escapeHtml(booking.booking_date)}</td>
      <td>${escapeHtml(booking.room_code)}</td>
      <td>${escapeHtml(prettyTime(booking.start_time))}–${escapeHtml(prettyTime(booking.end_time))}</td>
      <td>${escapeHtml(booking.purpose)}</td>
      <td><span class="pill">${escapeHtml(booking.status)}</span></td>
    </tr>
  `).join("") || `<tr><td colspan="6">No bookings yet.</td></tr>`;

  if ($("bookingRows")) $("bookingRows").innerHTML = rows;
  if ($("adminBookingRows")) $("adminBookingRows").innerHTML = rows;
  if ($("facultyRecentBookingRows")) {
    $("facultyRecentBookingRows").innerHTML = bookings.slice(0, 5).map((booking) => `
      <tr><td>#${escapeHtml(booking.booking_id)}</td><td>${escapeHtml(booking.booking_date)}</td>
      <td>${escapeHtml(booking.room_code)}</td><td>${escapeHtml(prettyTime(booking.start_time))}–${escapeHtml(prettyTime(booking.end_time))}</td>
      <td>${escapeHtml(booking.purpose)}</td><td><span class="pill">${escapeHtml(booking.status)}</span></td></tr>
    `).join("") || `<tr><td colspan="6">No bookings yet.</td></tr>`;
  }

  const count = bookings.length;
  ["facultyBookingMetric", "adminBookingMetric", "analysisBookingCount"].forEach(id => {
    if ($(id)) $(id).textContent = count;
  });
  renderAdminSchedule(bookings);
  
}
async function loadHealth() {
  try {
    const health = await api("/api/health");

    if ($("dbStatus")) {
      $("dbStatus").textContent =
        health.database === "ok" ? "Connected" : "Unavailable";
    }

    if ($("workerStatus")) {
      $("workerStatus").textContent =
        health.worker?.available ? "Online" : "Offline";
    }
  } catch {
    if ($("dbStatus")) $("dbStatus").textContent = "Unavailable";
    if ($("workerStatus")) $("workerStatus").textContent = "Offline";
  }
}

// -------------------- ADMIN REQUESTS --------------------

async function loadRequests() {
  try {
    const data = await api("/api/admin/requests");
    const tickets = data.requests || data.tickets || [];
    const pending = tickets.filter(ticket => String(ticket.status || "PENDING").toUpperCase() === "PENDING");
    const ticketRows = pending.map(ticket => {
      const id = ticket.ticket_id ?? ticket.request_id;
      const faculty = ticket.faculty_name || ticket.requester || ticket.faculty_email || "Faculty";
      const current = `${ticket.current_day || "—"} ${ticket.current_slot_label || ticket.current_slot_id || ""}`;
      const requested = `${ticket.requested_day || ticket.requested_date || "—"} ${ticket.requested_slot_label || ticket.slot_label || ticket.requested_slot_id || ""}`;
      return `<tr><td>#${escapeHtml(id)}</td><td>${escapeHtml(faculty)}</td><td>${escapeHtml(current)}</td><td>${escapeHtml(requested)}${ticket.requested_classroom ? `<br><small>${escapeHtml(ticket.requested_classroom)}</small>` : ""}</td><td>${escapeHtml(ticket.reason || ticket.purpose || "")}</td><td><div class="decision"><button data-id="${Number(id)}" data-decision="APPROVED">Approve</button><button class="reject" data-id="${Number(id)}" data-decision="REJECTED">Reject</button></div></td></tr>`;
    }).join("") || `<tr><td colspan="6">No pending timetable tickets.</td></tr>`;
    ["requestRows", "adminRecentTicketRows"].forEach(id => { if ($(id)) $(id).innerHTML = ticketRows; });
    const count = pending.length;
    ["pendingTicketBadge", "adminTicketMetric"].forEach(id => { if ($(id)) $(id).textContent = count; });
    if ($("pendingTicketLabel")) $("pendingTicketLabel").textContent = `${count} pending`;
    if ($("facultyTicketMetric")) $("facultyTicketMetric").textContent = "—";
    await loadScheduleChangeHistory();
  } catch (error) {
    message("globalMessage", `Could not load timetable tickets: ${error.message}`, "error");
    if ($("requestRows")) $("requestRows").innerHTML = `<tr><td colspan="6">Ticket service unavailable.</td></tr>`;
  }
}

async function loadScheduleChangeHistory() {
  if (!$("scheduleChangeHistoryRows")) return;
  try {
    const data = await api("/api/admin/schedule-change-requests/history");
    const rows = data.requests || data.tickets || data.history || [];
    $("scheduleChangeHistoryRows").innerHTML = rows.map(ticket => `
      <tr><td>#${escapeHtml(ticket.ticket_id ?? ticket.request_id)}</td><td>${escapeHtml(ticket.faculty_name || ticket.requester || ticket.faculty_email || "Faculty")}</td>
      <td>${escapeHtml(ticket.current_day || "—")} ${escapeHtml(ticket.current_slot_label || ticket.current_slot_id || "")}</td>
      <td>${escapeHtml(ticket.requested_day || "—")} ${escapeHtml(ticket.requested_slot_label || ticket.requested_slot_id || "")}</td>
      <td>${escapeHtml(ticket.reason || "")}</td>
      <td>
        <span class="pill status-${String(ticket.status || "").toLowerCase()}">
          ${escapeHtml(ticket.status || "")}
        </span>
      </td>
      <td>${escapeHtml(ticket.review_note || ticket.admin_note || "")}</td><td>${escapeHtml(ticket.reviewed_by_name || ticket.reviewer || ticket.reviewed_by || "—")}</td></tr>
    `).join("") || `<tr><td colspan="8">No reviewed tickets yet.</td></tr>`;
  } catch (error) {
    $("scheduleChangeHistoryRows").innerHTML = `<tr><td colspan="8">Ticket history could not be loaded.</td></tr>`;
  }
}
// -------------------- LOGIN AND DASHBOARDS --------------------


async function showApp(user) {
  if (!user || !user.role) {
    console.error("Invalid user information:", user);
    throw new Error("Unable to determine the logged-in user's role.");
  }

  const role = String(user.role).toUpperCase();

  if (!["ADMIN", "FACULTY"].includes(role)) {
    throw new Error("Invalid user role.");
  }

  currentUser = { ...user, role };

  $("loginPanel").hidden = true;
  $("appPanel").hidden = false;

  $("welcomeTitle").textContent =
    `Hello, ${user.name || user.email || "there"}`;

  $("welcomeSubtitle").textContent =
    role === "ADMIN"
      ? "Manage classroom resources, schedules and timetable tickets."
      : "Create room bookings and manage your teaching schedule.";

  $("roleEyebrow").textContent =
    role === "ADMIN" ? "ADMINISTRATION" : "FACULTY WORKSPACE";

  $("sessionArea").textContent =
    `${user.name || user.email} · ${role}`;

  $("facultyNav").hidden = role !== "FACULTY";
  $("adminNav").hidden = role !== "ADMIN";
  $("facultyBookingPanel").hidden = role !== "FACULTY";

  if ($("bookingDate") && !$("bookingDate").value) {
    $("bookingDate").value = localToday;
  }

  if ($("recurringStartDate") && !$("recurringStartDate").value) {
    $("recurringStartDate").value = localToday;
  }

  const homeView = role === "ADMIN" ? "adminHome" : "facultyHome";
  showView(homeView);

  try {
    await loadTimeSlots();
  } catch (error) {
    console.error("Time slots could not be loaded:", error);
    message("globalMessage", "Could not load database time slots.", "error");
  }

  const tasks = role === "ADMIN"
    ? [
        ["Rooms", loadRooms],
        ["Bookings", loadBookings],
        ["Health", loadHealth],
        ["Requests", loadRequests],
        ["Admin analysis", loadAdminAnalysis]
      ]
    : [
        ["Rooms", loadRooms],
        ["Bookings", loadBookings],
        ["Health", loadHealth],
        ["Faculty schedule", loadFacultySchedule],
        ["Booking form options", loadScheduleChangeFormOptions],
        ["Faculty tickets", loadFacultyTickets]
      ];

  const results = await Promise.allSettled(
    tasks.map(async ([name, loader]) => {
      try {
        await loader();
      } catch (error) {
        console.error(`${name} loading failed:`, error);
      }
    })
  );

  console.log(`${role} dashboard initialized.`, results);
  showView(homeView);
}

async function trySession() {
  try {
    const user = await api("/api/me");
    await showApp(user);
  } catch (error) {
    console.log("No active session:", error.message);
    $("appPanel").hidden = true;
    $("loginPanel").hidden = false;
  }
}

$("loginForm")?.addEventListener("submit", async (event) => {
  event.preventDefault();

  try {
    const result = await api("/api/login", {
      method: "POST",
      body: JSON.stringify({
        email: $("email").value,
        password: $("password").value
      })
    });

    message("loginMessage", "Signed in successfully.");
    await showApp(result.user);

  } catch (error) {
    message("loginMessage", error.message, "error");
  }
});

$("logoutBtn")?.addEventListener("click", async () => {
  try {
    await api("/api/logout", {
      method: "POST",
      body: "{}"
    });
  } catch (error) {
    console.error("Logout error:", error);
  }

  currentUser = null;

  if ($("appPanel")) $("appPanel").hidden = true;
  if ($("loginPanel")) $("loginPanel").hidden = false;

  if ($("sessionArea")) {
    $("sessionArea").innerHTML =
      '<span class="status-dot"></span> Demo environment';
  }
});

// -------------------- BOOKING TYPE --------------------

