// Faculty timetable view and refresh behavior.
const scheduleDays = [
  "MONDAY",
  "TUESDAY",
  "WEDNESDAY",
  "THURSDAY",
  "FRIDAY",
  "SATURDAY"
];

async function loadFacultySchedule() {
  const panel = $("facultySchedulePanel");
  if (!panel) return;

  panel.hidden = false;

  try {
    const data = await api("/api/faculty/my-schedule");

    const slots = data.slots || [];
    const regularEntries = data.regular_entries || [];
    const bookings = data.bookings || [];

    $("scheduleHead").innerHTML = `
      <tr>
        <th>Day</th>
        ${slots.map(slot => `
          <th>
            ${escapeHtml(slot.slot_label)}
            <small>
              ${escapeHtml(prettyTime(slot.start_time))}
              –${escapeHtml(prettyTime(slot.end_time))}
            </small>
          </th>
        `).join("")}
      </tr>
    `;

    const cells = {};

    function addCell(day, slotId, entry) {
      const key = `${day}|${slotId}`;
      if (!cells[key]) cells[key] = [];
      cells[key].push(entry);
    }

    regularEntries.forEach(entry => {
      addCell(entry.day_of_week, entry.slot_id, {
        type: "regular",
        title: entry.activity_name,
        room: entry.room_code
      });
    });

    // bookings.forEach(booking => {
    //   // JavaScript getUTCDay(): Sunday = 0, Monday = 1, ..., Saturday = 6.
    //   const dateString = String(booking.booking_date).slice(0, 10);
    //   const [year, month, dayOfMonth] = dateString.split("-").map(Number);

    //   const date = new Date(Date.UTC(year, month - 1, dayOfMonth));
    //   const dayIndex = date.getUTCDay();

    //   if (dayIndex === 0) return;

    //   const day = scheduleDays[dayIndex - 1];

    //   const type = booking.booking_type === "PERMANENT"
    //     ? "permanent"
    //     : "temporary";

    //   addCell(day, booking.slot_id, {
    //     type,
    //     title: booking.activity_name || (
    //       type === "permanent" ? "Permanent booking" : "Temporary booking"
    //     ),
    //     room: booking.room_code,
    //     date: booking.booking_date
    //   });
    //});



    bookings.forEach(booking => {
      const dateString = String(booking.booking_date).slice(0, 10);
      const [year, month, dayOfMonth] = dateString.split("-").map(Number);

      const date = new Date(Date.UTC(year, month - 1, dayOfMonth));
      const dayIndex = date.getUTCDay();

      if (dayIndex === 0) return;

      const day = scheduleDays[dayIndex - 1];

      const type = String(booking.booking_type).toUpperCase() === "PERMANENT"
      ? "recurring"
      : "one-day";

      addCell(day, booking.slot_id, {
        type,
        title: booking.activity_name || "Classroom booking",
        room: booking.room_code,
        date: dateString
      });
    });



    $("scheduleBody").innerHTML = scheduleDays.map(day => `
      <tr>
        <th>${day.charAt(0) + day.slice(1).toLowerCase()}</th>

        ${slots.map(slot => {
          const entries = cells[`${day}|${slot.slot_id}`] || [];

          if (!entries.length) {
            return `<td class="schedule-free">Free</td>`;
          }

          return `
            <td>
              ${entries.map(entry => `
                <div class="schedule-entry schedule-${entry.type}">
                  <strong>${escapeHtml(entry.title || "Scheduled activity")}</strong>
                  <span>${escapeHtml(entry.room || "Room not assigned")}</span>
                  ${entry.date
                    ? `<small>${escapeHtml(entry.date)}</small>`
                    : ""}
                </div>
              `).join("")}
            </td>
          `;
        }).join("")}
      </tr>
    `).join("");

    message("scheduleMessage", "Schedule loaded successfully.");

  } catch (error) {
    message("scheduleMessage", error.message, "error");
  }
}

$("refreshScheduleBtn")?.addEventListener(
  "click",
  loadFacultySchedule
);



["filterRoomType", "filterMinCapacity", "sortRooms"].forEach((id) => {
  $(id)?.addEventListener("input", () => {
    if (availableRoomResults.length) {
      renderAvailableRooms(
        window.currentSlotLabel || "Selected time slot"
      );
    }
  });
});





// Initialize the application.


// -------------------- ROLE-BASED SIDEBAR NAVIGATION --------------------
