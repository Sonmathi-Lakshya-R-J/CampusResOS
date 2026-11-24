
// Admin classroom timetable and weekly utilization.

let cachedBookings = [];
let cachedRegularEntries = [];
let adminWeekOffset = 0;

const adminScheduleDays = [
  "MONDAY",
  "TUESDAY",
  "WEDNESDAY",
  "THURSDAY",
  "FRIDAY",
  "SATURDAY"
];

let adminTimeSlots = [];

function getAdminWeekStart() {
  const date = new Date();
  date.setHours(12, 0, 0, 0);

  const day = date.getDay();
  date.setDate(date.getDate() - (day === 0 ? 6 : day - 1));
  date.setDate(date.getDate() + adminWeekOffset * 7);

  return [
    date.getFullYear(),
    String(date.getMonth() + 1).padStart(2, "0"),
    String(date.getDate()).padStart(2, "0")
  ].join("-");
}

function shiftAdminDate(dateString, days) {
  const date = new Date(`${dateString}T12:00:00`);
  date.setDate(date.getDate() + days);

  return [
    date.getFullYear(),
    String(date.getMonth() + 1).padStart(2, "0"),
    String(date.getDate()).padStart(2, "0")
  ].join("-");
}

function renderAdminSchedule(bookings) {
  const body = $("adminRoomScheduleRows");
  if (!body) return;

  const header = $("adminRoomScheduleHeader");
  if (header) {
    header.innerHTML =
      "<th>Day</th>" +
      adminTimeSlots.map(slot =>
        `<th>${escapeHtml(slot.label)}</th>`
      ).join("");
  }

  const roomId = $("adminRoomSelect")?.value;
  const weekStart = getAdminWeekStart();
  const weekEnd = shiftAdminDate(weekStart, 5);


  const todayWeekStart = (() => {
  const previousOffset = adminWeekOffset;
  adminWeekOffset = 0;
  const result = getAdminWeekStart();
  adminWeekOffset = previousOffset;
  return result;
})();

const weekLabel = $("adminWeekLabel");

if (weekLabel) {
  if (adminWeekOffset === 0) {
    weekLabel.textContent = "Current Week";
  } else if (adminWeekOffset === 1) {
    weekLabel.textContent = "Next Week";
  } else if (adminWeekOffset === -1) {
    weekLabel.textContent = "Previous Week";
  } else {
    weekLabel.textContent = `${weekStart} to ${weekEnd}`;
  }
}


  if (!roomId) {
    body.innerHTML = `
      <tr>
        <td colspan="${adminTimeSlots.length + 1}">Select a classroom to view its timetable.</td>
      </tr>
    `;

    $("weeklyUtilization").textContent = "0%";
    $("weeklyUtilizationBar").style.width = "0%";
    return;
  }

  const weeklyBookings = (bookings || []).filter(booking => {
    const date = String(booking.booking_date).slice(0, 10);

    return (
      String(booking.classroom_id) === String(roomId) &&
      date >= weekStart &&
      date <= weekEnd &&
      String(booking.status).toUpperCase() === "CONFIRMED"
    );
  });

  const regularClasses = (cachedRegularEntries || []).filter(entry =>
    String(entry.classroom_id) === String(roomId)
  );

  const occupied = new Set();

  body.innerHTML = adminScheduleDays.map((day, dayIndex) => {
    const date = shiftAdminDate(weekStart, dayIndex);

    const regularForDay = regularClasses.filter(entry =>
      String(entry.day_of_week).toUpperCase() === day
    );

    const cells = adminTimeSlots.map(slot => {
      const regularMatches = regularForDay.filter(entry =>
        String(entry.slot_id) === String(slot.id)
      );

      const bookingMatches = weeklyBookings.filter(booking =>
        String(booking.booking_date).slice(0, 10) === date &&
        String(booking.slot_id) === String(slot.id)
      );

      if (regularMatches.length || bookingMatches.length) {
        // Count the slot once even if both sources contain an entry.
        occupied.add(`${date}|${slot.id}`);

        const regularHtml = regularMatches.map(entry => `
          <div class="schedule-entry schedule-regular">
            <strong>${escapeHtml(entry.activity_name || "Regular class")}</strong>
            <small>${escapeHtml(entry.activity_type || "CLASS")}</small>
          </div>
        `).join("");

        const bookingHtml = bookingMatches.map(booking => `
          <div class="schedule-entry schedule-booked-entry">
            <strong>${escapeHtml(booking.purpose || "Confirmed booking")}</strong>
            <small>${escapeHtml(booking.requester || "")}</small>
          </div>
        `).join("");

        return `
          <td class="schedule-booked">
            ${regularHtml}
            ${bookingHtml}
          </td>
        `;
      }

      return `<td class="schedule-free">Free</td>`;
    }).join("");

    const dayLabel = day.charAt(0) + day.slice(1).toLowerCase();

    return `
      <tr>
        <th>
          ${dayLabel}
          <small>${date}</small>
        </th>
        ${cells}
      </tr>
    `;
  }).join("");

  const totalSlots = adminScheduleDays.length * adminTimeSlots.length;
  const percentage = (occupied.size / totalSlots) * 100;

  $("weeklyUtilization").textContent = `${percentage.toFixed(2)}%`;
  $("weeklyUtilizationBar").style.width = `${percentage}%`;

  $("weeklyUtilizationBar").parentElement.setAttribute(
    "aria-valuenow",
    percentage.toFixed(2)
  );
}





async function loadAdminAnalysis() {
  try {
    const [roomData, bookingData, regularData, analyticsData] = await Promise.all([
    api("/api/rooms"),
    api("/api/bookings"),
    api("/api/admin/regular-classes"),
    api("/api/admin/analytics")
]);
    const rooms = roomData.rooms || [];
    cachedBookings = bookingData.bookings || [];

    const utilizationRooms = analyticsData.rooms || [];

const usedRooms = utilizationRooms.filter(
    room => Number(room.confirmed_bookings) > 0
);

if ($("analysisUsedRoomCount")) {
    $("analysisUsedRoomCount").textContent = usedRooms.length;
}

if ($("utilizationRows")) {
    $("utilizationRows").innerHTML = utilizationRooms.map(room => `
        <div class="utilization-row">
            <div>
                <strong>${escapeHtml(room.room_code)}</strong>
                <small>${Number(room.confirmed_bookings)} confirmed bookings</small>
            </div>
        </div>
    `).join("");
}

    // cachedRegularClasses = regularData.regular_entries || [];
    cachedRegularEntries = regularData.regular_entries || [];

    adminTimeSlots = (cachedTimeSlots || []).map(slot => ({
      id: Number(slot.slot_id),
      label: slot.slot_label
    }));

    
    const select = $("adminRoomSelect");

    if (select) {
      const previousRoom = select.value;

      select.innerHTML = rooms.map(room => `
        <option value="${Number(room.classroom_id)}">
          ${escapeHtml(room.room_code)} · ${escapeHtml(room.room_name || "")}
        </option>
      `).join("");

      if (rooms.some(room =>
        String(room.classroom_id) === previousRoom
      )) {
        select.value = previousRoom;
      } else if (rooms.length > 0) {
        select.value = String(rooms[0].classroom_id);
      }
    }

    if ($("roomCount")) {
      $("roomCount").textContent = rooms.length;
    }

    if ($("adminRoomMetric")) {
      $("adminRoomMetric").textContent = rooms.length;
    }

    if ($("facultyRoomMetric")) {
      $("facultyRoomMetric").textContent = rooms.length;
    }

    if ($("analysisRoomCount")) {
      $("analysisRoomCount").textContent = rooms.length;
    }

    if ($("analysisBookingCount")) {
      $("analysisBookingCount").textContent = cachedBookings.length;
    }

    renderAdminSchedule(cachedBookings);

  } catch (error) {
    message(
      "globalMessage",
      `Analysis could not be loaded: ${error.message}`,
      "error"
    );
  }
}




// Refresh timetable when either filter changes.
$("adminRoomSelect")?.addEventListener("change", () => {
  renderAdminSchedule(cachedBookings);
});

$("adminPrevWeek")?.addEventListener("click", () => {
  adminWeekOffset--;
  renderAdminSchedule(cachedBookings);
});

$("adminNextWeek")?.addEventListener("click", () => {
  adminWeekOffset++;
  renderAdminSchedule(cachedBookings);
});