// Booking search, one-day booking, recurring booking, availability, and confirmation.
let cachedTimeSlots = [];

function updateTimeSlotAvailability() {
  const select = $("timeSlot");
  if (!select) return;

  const dates = getSearchDates();
  const today = localToday;
  const now = new Date();
  const currentMinutes = now.getHours() * 60 + now.getMinutes();

  [...select.options].forEach(option => {
    if (!option.value) return;

    const slot = cachedTimeSlots.find(
      item => String(item.slot_id) === option.value
    );
    if (!slot) return;

    const start = String(slot.start_time || "00:00:00");
    const [hours, minutes] = start.split(":").map(Number);
    const alreadyStarted = dates.includes(today) &&
      hours * 60 + minutes <= currentMinutes;

    option.disabled = alreadyStarted;
    option.textContent = slot.slot_label +
      (alreadyStarted ? " (already started)" : "");
  });

  const selected = select.selectedOptions[0];
  if (selected?.disabled) select.value = "";
}

async function loadTimeSlots() {
  const data = await api("/api/time-slots");
  cachedTimeSlots = data.slots || [];

  const select = $("timeSlot");
  if (!select) return;

  const previousValue = select.value;

  select.innerHTML =
    '<option value="">Select a time slot</option>' +
    cachedTimeSlots.map(slot => `
      <option value="${Number(slot.slot_id)}">
        ${escapeHtml(slot.slot_label)}
      </option>
    `).join("");

  if (cachedTimeSlots.some(
    slot => String(slot.slot_id) === previousValue
  )) {
    select.value = previousValue;
  }

  updateTimeSlotAvailability();
}

function selectedBookingType() {
  return $("bookingType")?.value || "TEMPORARY";
}

function clearSearchResults() {
  selectedRoom = null;
  searchedDates = [];
  availableRoomResults = [];

  if ($("availableRooms")) {
    $("availableRooms").innerHTML = "";
  }

  if ($("availableRoomsSection")) {
    $("availableRoomsSection").hidden = true;
  }

  if ($("bookingConfirmSection")) {
    $("bookingConfirmSection").hidden = true;
  }
}

function configureBookingType() {
  const type = selectedBookingType();

  if ($("oneDayFields")) {
    $("oneDayFields").hidden = type !== "TEMPORARY";
  }

  if ($("recurringFields")) {
    $("recurringFields").hidden = type !== "PERMANENT";
  }

  clearSearchResults();
  message("bookingMessage", "");
}

$("bookingType")?.addEventListener("change", () => {
  configureBookingType();
  updateTimeSlotAvailability();
});

// -------------------- GENERATE BOOKING DATES --------------------
function getSearchDates() {
  const type = selectedBookingType();

  // One-day booking.
  if (type === "TEMPORARY") {
    const date = $("bookingDate")?.value;
    return date ? [date] : [];
  }

  // Recurring weekly booking.
  const startText = $("recurringStartDate")?.value;
  const weeks = Number($("bookingWeeks")?.value);

  if (
    !startText ||
    !Number.isInteger(weeks) ||
    weeks < 1 ||
    weeks > 52
  ) {
    return [];
  }

  const start = new Date(`${startText}T12:00:00`);

  if (Number.isNaN(start.getTime())) {
    return [];
  }

  const dates = [];

  for (let index = 0; index < weeks; index++) {
    const occurrence = new Date(start);
    occurrence.setDate(start.getDate() + index * 7);

    dates.push(
      `${occurrence.getFullYear()}-${String(occurrence.getMonth() + 1).padStart(2, "0")}-${String(occurrence.getDate()).padStart(2, "0")}`
    );
  }

  return dates;
}
// Show the custom purpose field only when "Others" is selected.
$("bookingPurpose")?.addEventListener("change", () => {
  const isOther = $("bookingPurpose").value === "Others";
  const otherField = $("otherPurposeField");

  if (otherField) {
    otherField.hidden = !isOther;
  }

  if (!isOther && $("otherPurposeText")) {
    $("otherPurposeText").value = "";
  }
});

// -------------------- FIND AVAILABLE CLASSROOMS --------------------

$("bookingSearchForm")?.addEventListener("submit", async (event) => {
  event.preventDefault();

  clearSearchResults();

  if (currentUser?.role !== "FACULTY") {
    message("bookingMessage", "Only faculty can create bookings.", "error");
    return;
  }

  updateTimeSlotAvailability();

  const slotId = Number($("timeSlot")?.value);
  const dates = getSearchDates();

  if (!slotId) {
    message("bookingMessage", "Please select a time slot.", "error");
    return;
  }

  if (!dates.length) {
    message(
      "bookingMessage",
      "Enter a valid date and a duration between 1 and 52 weeks.",
      "error"
    );
    return;
  }

  if (dates.some((date) => date < localToday)) {
    message(
      "bookingMessage",
      "Bookings cannot include past dates.",
      "error"
    );
    return;
  }

  const button = $("findRoomsBtn");
  if (button) button.disabled = true;

  try {
    const type = selectedBookingType();
    let result;

    if (type === "TEMPORARY") {
      // Implemented in the updated Flask backend.
      result = await api(
        `/api/available-rooms?booking_date=${encodeURIComponent(dates[0])}&slot_id=${slotId}`
      );

      searchedDates = dates;

      availableRoomResults = (result.rooms || []).map((room) => ({
        ...room,
        availableDates: dates,
        unavailable: []
      }));

    } else {
      // Requires the recurring availability API in Flask.
      result = await api("/api/recurring/availability", {
        method: "POST",
        body: JSON.stringify({
          dates,
          slot_id: slotId
        })
      });

      searchedDates = dates;
      availableRoomResults = result.rooms || [];
    }

    renderAvailableRooms(
      result.slot?.slot_label ||
      result.slot_label ||
      `Slot ${slotId}`
    );

    if (availableRoomResults.length) {
      message(
        "bookingMessage",
        `${availableRoomResults.length} classroom(s) found. Select a classroom to continue.`
      );
    } else {
      message(
        "bookingMessage",
        "No classrooms are available for these dates and this time slot.",
        "error"
      );
    }

  } catch (error) {
    window.alert(error.message);
    message("bookingMessage", error.message, "error");
  } finally {
    if (button) button.disabled = false;
  }
});

// -------------------- DISPLAY AVAILABLE ROOMS --------------------

// function renderAvailableRooms(slotLabel) {
//   if (!$("availableRooms") || !$("availableRoomsSection")) {
//     return;
//   }

//   $("availableRooms").innerHTML = availableRoomResults.map((room) => {
//     const availableDates = room.availableDates || searchedDates;
//     const unavailableDates = room.unavailable || [];

//     return `
//       <article class="room-card">
//         <h4>
//           ${escapeHtml(room.room_code)}
//           ·
//           ${escapeHtml(room.room_name)}
//         </h4>

//         <p>
//           Capacity: ${escapeHtml(room.capacity)}<br>
//           Time slot: ${escapeHtml(slotLabel)}<br>
//           Available dates: ${availableDates.length}
//           ${unavailableDates.length
//             ? `<br>Unavailable dates: ${unavailableDates.length}`
//             : ""}
//         </p>

//         <button
//           type="button"
//           data-room-id="${Number(room.classroom_id)}">
//           Select classroom
//         </button>
//       </article>
//     `;
//   }).join("") ||
//     `<p class="muted">No available classrooms found.</p>`;

//   $("availableRoomsSection").hidden = false;

//   $("availableRooms")
//     .querySelectorAll("button[data-room-id]")
//     .forEach((button) => {
//       button.addEventListener("click", () => {
//         selectRoom(Number(button.dataset.roomId));
//       });
//     });
// }









// function normalizeRoomType(room) {
//   const value = String(
//     room.room_type || room.room_code || ""
//   ).trim().toUpperCase();

//   if (value === "LT" || value.startsWith("LT-") ||
//       value.startsWith("LT ")) {
//     return "LT";
//   }

//   if (value === "LAB" || value.includes("LAB")) {
//     return "LAB";
//   }

//   if (value === "CR" || value.startsWith("CR-") ||
//       value.startsWith("CR ")) {
//     return "CR";
//   }

//   // If room_type is a descriptive value, recognize common labels.
//   if (value.includes("LECTURE HALL")) return "LT";
//   if (value.includes("CLASSROOM")) return "CR";

//   return "OTHER";
// }





function normalizeRoomType(room) {
  const value = String(room.room_type || "").trim().toUpperCase();

  if (value === "CLASSROOM" || value === "CR") return "CR";
  if (value === "LAB" || value === "LABORATORY") return "LAB";
  if (value === "SEMINAR_HALL" || value === "SEMINAR HALL") return "SEMINAR_HALL";
  if (value === "LT" || value === "LECTURE_HALL" || value === "LECTURE HALL") return "LT";

  return "OTHER";
}


function getFilteredRooms() {
  const selectedType = $("filterRoomType")?.value || "ALL";
  const minCapacity = Math.max(
    0,
    Number($("filterMinCapacity")?.value || 0)
  );
  const sortBy = $("sortRooms")?.value || "recommended";

  const rooms = availableRoomResults.filter(room => {
    const capacity = Number(room.capacity || 0);
    const type = normalizeRoomType(room);

    const matchesType =
      selectedType === "ALL" || type === selectedType;

    const matchesCapacity = capacity >= minCapacity;

    return matchesType && matchesCapacity;
  });

  rooms.sort((a, b) => {
    if (sortBy === "capacity-asc") {
      return Number(a.capacity) - Number(b.capacity);
    }

    if (sortBy === "capacity-desc") {
      return Number(b.capacity) - Number(a.capacity);
    }

    if (sortBy === "name-asc") {
      return String(a.room_code || "").localeCompare(
        String(b.room_code || "")
      );
    }

    // Recommended: prefer rooms that fit the requirement
    // without unnecessarily choosing the largest room.
    return Number(a.capacity) - Number(b.capacity);
  });

  return rooms;
}

function renderAvailableRooms(slotLabel) {
  window.currentSlotLabel = slotLabel;
  if (!$("availableRooms") || !$("availableRoomsSection")) return;

  const rooms = getFilteredRooms();

  if ($("roomResultCount")) {
    $("roomResultCount").textContent =
      `Showing ${rooms.length} of ${availableRoomResults.length} available room(s).`;
  }

  $("availableRooms").innerHTML = rooms.map(room => {
    const type = normalizeRoomType(room);

    const typeLabel = {
      CR: "Classroom",
      LAB: "Laboratory",
      SEMINAR_HALL: "Seminar Hall",
      LT: "Lecture Hall",
      OTHER: "Other"
    }[type];
    // Backend returns snake_case for recurring availability.
    const availableDates =
      room.available_dates || room.availableDates || searchedDates;

    const unavailableDates =
      room.unavailable_dates || room.unavailable || [];

    return `
      <article class="room-card">
        <span class="room-type-badge">${escapeHtml(typeLabel)}</span>

        <h4>
          ${escapeHtml(room.room_code)}
          · ${escapeHtml(room.room_name)}
        </h4>

        <p class="room-capacity">
          Capacity: ${escapeHtml(room.capacity)} seats
        </p>

        <p>
          Time: ${escapeHtml(slotLabel)}<br>
          Available dates: ${availableDates.length}
          ${unavailableDates.length
            ? `<br>Unavailable dates: ${unavailableDates.length}`
            : ""}
        </p>

        <button
          type="button"
          data-room-id="${room.classroom_id}"
        >
          Select classroom
        </button>
      </article>
    `;
  }).join("") || `
    <p class="muted">
      No rooms match these filters. Try a lower capacity or another room type.
    </p>
  `;

  $("availableRoomsSection").hidden = false;

  $("availableRooms")
    .querySelectorAll("button[data-room-id]")
    .forEach(button => {
      button.addEventListener("click", () => {
        selectRoom(Number(button.dataset.roomId));
      });
    });
}












// -------------------- SELECT A CLASSROOM --------------------

function selectRoom(roomId) {
  selectedRoom = availableRoomResults.find(
    (room) => Number(room.classroom_id) === roomId
  );

  if (!selectedRoom) return;

  if ($("selectedRoomSummary")) {
    $("selectedRoomSummary").textContent =
      `${selectedRoom.room_code} · ${selectedRoom.room_name} · ${selectedRoom.capacity} seats`;
  }

  if ($("bookingDatesSummary")) {
    const availableDates =
      selectedRoom.available_dates ||
      selectedRoom.availableDates ||
      searchedDates;

    const unavailableDates =
      selectedRoom.unavailable_dates ||
      selectedRoom.unavailable ||
      [];

    const items = [
      `<strong>Dates to book (${availableDates.length})</strong>`,
      ...availableDates.map((date) =>
        `<div class="date-item">${escapeHtml(date)}</div>`
      )
    ];

    if (unavailableDates.length) {
      items.push(
        `<strong>Unavailable dates (${unavailableDates.length})</strong>`
      );

      unavailableDates.forEach((item) => {
        items.push(
          `<div class="date-item">${escapeHtml(item.date)}: ${escapeHtml(item.reason || "Unavailable")}</div>`
        );
      });
    }

    $("bookingDatesSummary").innerHTML = items.join("");
  }

  if ($("bookingConfirmSection")) {
    $("bookingConfirmSection").hidden = false;
  }

  $("bookingPurpose")?.focus();
}

// -------------------- CANCEL BOOKING CONFIRMATION --------------------

$("cancelBookingBtn")?.addEventListener("click", () => {
  if ($("bookingConfirmSection")) {
    $("bookingConfirmSection").hidden = true;
  }

  selectedRoom = null;
});

// -------------------- CONFIRM BOOKING --------------------

$("confirmBookingBtn")?.addEventListener("click", async () => {
  if (currentUser?.role !== "FACULTY") {
    message("bookingMessage", "Only faculty can create bookings.", "error");
    return;
  }

  if (!selectedRoom) {
    message("bookingMessage", "Select a classroom first.", "error");
    return;
  }

  const selectedPurpose = $("bookingPurpose")?.value.trim() || "";
  const otherText = $("otherPurposeText")?.value.trim() || "";

  if (!selectedPurpose) {
    message("bookingMessage", "Please select a booking purpose.", "error");
    return;
  }

  if (selectedPurpose === "Others" && !otherText) {
    message("bookingMessage", "Please specify your booking purpose.", "error");
    $("otherPurposeText")?.focus();
    return;
  }

  const purpose = selectedPurpose === "Others"
    ? `Others: ${otherText}`
    : selectedPurpose;

  if (purpose.length > 255) {
    message("bookingMessage", "Purpose must be at most 255 characters.", "error");
    return;
  }

  const button = $("confirmBookingBtn");
  button.disabled = true;

  try {
    const type = selectedBookingType();
    let result;

    if (type === "TEMPORARY") {
      // The backend must recheck availability before inserting the booking.
      result = await api("/api/bookings", {
        method: "POST",
        body: JSON.stringify({
          classroom_id: Number(selectedRoom.classroom_id),
          booking_date: searchedDates[0],
          slot_id: Number($("timeSlot").value),
          purpose,
          confirm: true
        })
      });

      message(
        "bookingMessage",
        `Booking #${result.booking_id} confirmed.`
      );

    } else {
      // Requires the recurring booking API in Flask.
      result = await api("/api/recurring/bookings", {
        method: "POST",
        body: JSON.stringify({
          classroom_id: Number(selectedRoom.classroom_id),
          dates:
            selectedRoom.available_dates ||
            selectedRoom.availableDates ||
            searchedDates,
          slot_id: Number($("timeSlot").value),
          purpose,
          confirm: true
        })
      });

      const count =
        result.bookings_created ??
        result.bookings?.length ??
        0;

      message(
        "bookingMessage",
        `${count} recurring booking(s) confirmed.`
      );
    }

    if ($("bookingConfirmSection")) {
      $("bookingConfirmSection").hidden = true;
    }

    selectedRoom = null;

    await loadBookings();

    if (currentUser?.role === "FACULTY") {
      await loadFacultySchedule();
    }

  } catch (error) {
    window.alert(error.message);
    message("bookingMessage", error.message, "error");
  }
 finally {
    button.disabled = false;
  }
});

// -------------------- LEGACY ONE-DAY FORM --------------------
// Keeps the original form working if the redesigned HTML
// has not yet replaced it.

$("bookingForm")?.addEventListener("submit", async (event) => {
  event.preventDefault();

  if ($("bookingSearchForm")) return;

  if (currentUser?.role !== "FACULTY") {
    message("bookingMessage", "Only faculty can create bookings.", "error");
    return;
  }

  const button = event.submitter;
  if (button) button.disabled = true;

  try {
    const booking = {
      classroom_id: Number($("classroom")?.value),
      booking_date: $("bookingDate")?.value,
      slot_id: Number($("timeSlot")?.value),
      purpose: $("purpose")?.value.trim()
    };

    const preview = await api("/api/bookings", {
      method: "POST",
      body: JSON.stringify(booking)
    });

    if (!preview.needs_confirmation) {
      message(
        "bookingMessage",
        preview.message || "Unable to confirm availability.",
        "error"
      );
      return;
    }

    const confirmed = window.confirm(
      "The classroom is available. Confirm this booking?"
    );

    if (!confirmed) {
      message("bookingMessage", "Booking cancelled.");
      return;
    }

    const result = await api("/api/bookings", {
      method: "POST",
      body: JSON.stringify({
        ...booking,
        confirm: true
      })
    });

    message(
      "bookingMessage",
      `Booking #${result.booking_id} confirmed.`
    );

    await loadBookings();

  } catch (error) {
    message("bookingMessage", error.message, "error");
  } finally {
    if (button) button.disabled = false;
  }
});

// // -------------------- OS SCHEDULER --------------------

// $("runScheduleBtn")?.addEventListener("click", async () => {
//   if ($("scheduleOutput")) {
//     $("scheduleOutput").textContent = "Running...";
//   }

//   try {
//     const algorithm = $("algorithm")?.value || "FCFS";

//     const result = await api(
//       `/api/os/schedule?algorithm=${encodeURIComponent(algorithm)}`
//     );

//     if ($("scheduleOutput")) {
//       $("scheduleOutput").textContent =
//         result.worker_reply || JSON.stringify(result, null, 2);
//     }

//   } catch (error) {
//     if ($("scheduleOutput")) {
//       $("scheduleOutput").textContent = error.message;
//     }
//   }
// });

// -------------------- REFRESH DASHBOARD --------------------

$("refreshBtn")?.addEventListener("click", async () => {
  try {
    await Promise.all([
      loadBookings(),
      loadHealth()
    ]);

    message("globalMessage", "Dashboard refreshed.");

  } catch (error) {
    message("globalMessage", error.message, "error");
  }
});

// -------------------- ADMIN APPROVALS --------------------

$("requestRows")?.addEventListener("click", async (event) => {
  const button = event.target.closest("button[data-id]");

  if (!button) return;

  button.disabled = true;

  try {
    await api(
      `/api/admin/schedule-change-requests/${button.dataset.id}/decision`,
      {
        method: "POST",
        body: JSON.stringify({
          decision: button.dataset.decision
        })
      }
    );

    await Promise.all([
      loadRequests(),
      loadBookings()
    ]);

    message(
      "globalMessage",
      `Request ${button.dataset.id} ${button.dataset.decision.toLowerCase()}.`
    );

  } catch (error) {
    message("globalMessage", error.message, "error");
    button.disabled = false;
  }
});

// -------------------- INITIALIZATION --------------------

if ($("bookingDate")) {
  $("bookingDate").min = localToday;
  $("bookingDate").value = localToday;
}

if ($("recurringStartDate")) {
  $("recurringStartDate").min = localToday;
  $("recurringStartDate").value = localToday;
}

$("bookingDate")?.addEventListener("change", () => {
  clearSearchResults();
  updateTimeSlotAvailability();
});

$("recurringStartDate")?.addEventListener("change", () => {
  clearSearchResults();
  updateTimeSlotAvailability();
});

//
$("bookingWeeks")?.addEventListener("change", updateTimeSlotAvailability);





// ["filterRoomType", "filterMinCapacity", "sortRooms"].forEach(id => {
//   $(id)?.addEventListener("input", () => {
//     if (availableRoomResults.length) {
//       renderAvailableRooms(
//         window.currentSlotLabel || "Selected time slot"
//       );
//     }
//   });


// ["filterRoomType", "filterMinCapacity", "sortRooms"].forEach(id => {
//   $(id)?.addEventListener("input", () => {
//     if (availableRoomResults.length) {
//       renderAvailableRooms(
//         window.currentSlotLabel || "Selected time slot"
//       );
//     }
//   });
// });

//   $(id)?.addEventListener("change", () => {
//     if (availableRoomResults.length) {
//       renderAvailableRooms(
//         window.currentSlotLabel || "Selected time slot"
//       );
//     }
//   });
// });



// trySession();




