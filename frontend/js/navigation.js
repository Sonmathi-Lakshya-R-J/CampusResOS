// Role-based sidebar navigation and dashboard refresh controls.
function showView(viewId) {
  document.querySelectorAll(".view-section").forEach(section => {
    section.hidden = section.id !== viewId;
  });
  document.querySelectorAll(".nav-link").forEach(button => {
    button.classList.toggle("active", button.dataset.view === viewId);
  });
  const view = $(viewId);
  if (view) {
    const title = view.querySelector("h2");
    if (title) document.title = `CampusResOS | ${title.textContent}`;
  }
}
document.addEventListener("click", event => {
  const button = event.target.closest("[data-view]");
  if (!button) return;
  const viewId = button.dataset.view;
  if (currentUser?.role === "FACULTY" && !viewId.startsWith("faculty") && !["createBookingView","raiseTicketView","myBookingsView"].includes(viewId)) return;
  if (currentUser?.role === "ADMIN" && viewId.startsWith("faculty")) return;
  showView(viewId);
  if (viewId === "adminTicketsView") { loadRequests(); }
  if (viewId === "raiseTicketView") { loadScheduleChangeFormOptions(); loadFacultyTickets(); }
  if (viewId === "facultyScheduleView") loadFacultySchedule();
  if (viewId === "myBookingsView" || viewId === "adminBookingsView") loadBookings();
  if (viewId === "adminAnalysisView") loadAdminAnalysis();
});
$("logoutBtn")?.addEventListener("click", async () => {
  currentUser = null;
  $("appPanel").hidden = true;
  $("loginPanel").hidden = false;
  $("sessionArea").innerHTML = '<span class="status-dot"></span> Demo environment';
  document.querySelectorAll(".view-section").forEach(section => section.hidden = true);
});


$("facultyRefreshBtn")?.addEventListener("click", async () => {
  if (currentUser?.role !== "FACULTY") return;

  try {
    await Promise.all([
      loadRooms(),
      loadBookings(),
      loadHealth(),
      loadFacultySchedule(),
      loadFacultyTickets()
    ]);

    message("globalMessage", "Workspace refreshed.");
  } catch (error) {
    message("globalMessage", error.message, "error");
  }
});


$("adminRefreshBtn")?.addEventListener("click", async () => {
  try { await Promise.all([loadRooms(), loadBookings(), loadHealth(), loadRequests(), loadAdminAnalysis()]); message("globalMessage", "Administration overview refreshed."); }
  catch (error) { message("globalMessage", error.message, "error"); }
});
$("refreshRequestsBtn")?.addEventListener("click", loadRequests);
$("refreshHistoryBtn")?.addEventListener("click", loadScheduleChangeHistory);
$("refreshFacultyTicketsBtn")?.addEventListener("click", loadFacultyTickets);
$("adminBookingsRefreshBtn")?.addEventListener("click", loadBookings);
$("refreshAnalysisBtn")?.addEventListener("click", loadAdminAnalysis);
$("refreshScheduleBtn")?.addEventListener("click", loadFacultySchedule);

$("adminRecentTicketRows")?.addEventListener("click", async event => {
  const button = event.target.closest("button[data-id]");
  if (!button) return;
  button.disabled = true;
  try {
    await api(`/api/admin/schedule-change-requests/${button.dataset.id}/decision`, {
      method: "POST",
      body: JSON.stringify({decision: button.dataset.decision})
    });
    await Promise.all([loadRequests(), loadBookings()]);
    message("globalMessage", `Ticket #${button.dataset.id} ${button.dataset.decision.toLowerCase()}.`);
  } catch (error) {
    message("globalMessage", error.message, "error");
    button.disabled = false;
  }
});

// -------------------- FACULTY TIMETABLE CHANGE TICKETS --------------------
