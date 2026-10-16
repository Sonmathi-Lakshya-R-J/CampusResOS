#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <pthread.h>
#include <ctype.h>

#define MAX_JSON 2000000
#define MAX_TOKENS 50000
#define MAX_ROOMS 500
#define MAX_BOOKINGS 10000
#define MAX_TEXT 256

typedef enum {
    TOKEN_OBJECT,
    TOKEN_ARRAY,
    TOKEN_STRING,
    TOKEN_PRIMITIVE
} TokenType;

typedef struct {
    TokenType type;
    int start;
    int end;
    int size;
    int parent;
} Token;

typedef struct {
    char id[MAX_TEXT];
    char name[MAX_TEXT];
    int capacity;
    int active;
} Room;

typedef struct {
    char id[MAX_TEXT];
    char faculty[MAX_TEXT];
    char room[MAX_TEXT];
    char day[MAX_TEXT];
    char start[MAX_TEXT];
    char end[MAX_TEXT];
    char status[MAX_TEXT];
    int students;
    int priority;
    int processing_time;
    int waiting_time;
    int turnaround_time;
} Booking;

typedef struct {
    int index;
    int priority;
    int duration;
    int original_order;
} Job;

static char json[MAX_JSON];
static Token tokens[MAX_TOKENS];
static int token_count = 0;

static pthread_mutex_t mutex = PTHREAD_MUTEX_INITIALIZER;

static Room rooms[MAX_ROOMS];
static Booking bookings[MAX_BOOKINGS];

static int room_count = 0;
static int booking_count = 0;

/* Function declarations */

static int parse_json(void);
static int parse_value(int *position, int parent);
static int skip_whitespace(int *position);
static int find_key(int object_token, const char *key);
static int token_equals(int token, const char *value);
static void token_string(int token, char *output, size_t size);
static int token_integer(int token, int fallback);
static int time_to_minutes(const char *value);
static int intervals_overlap(const char *start1, const char *end1,
                             const char *start2, const char *end2);
static int find_room(const char *room_id);
static int is_active_status(const char *status);

static int is_room_available(const char *room_id,
                             const char *day,
                             const char *start,
                             const char *end,
                             int students,
                             char *reason,
                             size_t reason_size);

static int load_rooms(int array_token);
static int load_bookings(int array_token);
static int load_pending(int array_token,
                        Booking *pending,
                        int max_pending);

static void print_json_string(const char *value);
static void operation_check_room(int root);
static void operation_schedule(int root);
static int booking_duration(const Booking *booking);

static void print_booking_result(const Booking *booking,
                                 const char *result_status,
                                 const char *reason);

static void print_alternatives(const Booking *booking);
static int token_next(int token);


/* Skip whitespace */

static int skip_whitespace(int *position) {
    while (json[*position] &&
           isspace((unsigned char)json[*position])) {
        (*position)++;
    }

    return 1;
}


/* Parse one JSON value */

static int parse_value(int *position, int parent) {
    skip_whitespace(position);

    if (token_count >= MAX_TOKENS) {
        return -1;
    }

    int index = token_count++;
    Token *token = &tokens[index];

    token->start = *position;
    token->end = *position;
    token->size = 0;
    token->parent = parent;

    char c = json[*position];

    if (c == '{' || c == '[') {
        token->type = (c == '{') ? TOKEN_OBJECT : TOKEN_ARRAY;

        char closing = (c == '{') ? '}' : ']';

        (*position)++;

        while (1) {
            skip_whitespace(position);

            if (json[*position] == closing) {
                (*position)++;
                token->end = *position;
                return index;
            }

            if (json[*position] == '\0') {
                return -1;
            }

            if (json[*position] == ',' ||
                json[*position] == ':') {
                (*position)++;
                continue;
            }

            int child = parse_value(position, index);

            if (child < 0) {
                return -1;
            }

            token->size++;
        }
    }

    if (c == '"') {
        token->type = TOKEN_STRING;

        (*position)++;

        while (json[*position]) {
            if (json[*position] == '\\') {
                (*position) += json[*position + 1] ? 2 : 1;
                continue;
            }

            if (json[*position] == '"') {
                (*position)++;
                token->end = *position;
                return index;
            }

            (*position)++;
        }

        return -1;
    }

    token->type = TOKEN_PRIMITIVE;

    while (json[*position] &&
           json[*position] != ',' &&
           json[*position] != ']' &&
           json[*position] != '}' &&
           !isspace((unsigned char)json[*position])) {
        (*position)++;
    }

    token->end = *position;

    if (token->end == token->start) {
        return -1;
    }

    return index;
}


/* Parse the complete JSON input */

static int parse_json(void) {
    int position = 0;

    token_count = 0;

    skip_whitespace(&position);

    if (json[position] != '{') {
        return -1;
    }

    int root = parse_value(&position, -1);

    if (root < 0) {
        return -1;
    }

    skip_whitespace(&position);

    if (json[position] != '\0') {
        return -1;
    }

    return root;
}


/* Find the token following a JSON value */

static int token_next(int token) {
    if (token < 0 || token >= token_count) {
        return token_count;
    }

    int end = tokens[token].end;
    int next = token + 1;

    while (next < token_count &&
           tokens[next].start < end) {
        next++;
    }

    return next;
}


/* Copy a JSON token into a string */

static void token_string(int token, char *output, size_t size) {
    if (size == 0) {
        return;
    }

    output[0] = '\0';

    if (token < 0 || token >= token_count) {
        return;
    }

    Token *t = &tokens[token];

    int start = t->start;
    int end = t->end;

    if (t->type == TOKEN_STRING) {
        start++;
        end--;
    }

    size_t length = (size_t)(end - start);

    if (length >= size) {
        length = size - 1;
    }

    memcpy(output, json + start, length);

    output[length] = '\0';
}


/* Compare a JSON token with a string */

static int token_equals(int token, const char *value) {
    char buffer[MAX_TEXT];

    token_string(token, buffer, sizeof(buffer));

    return strcmp(buffer, value) == 0;
}


/* Find a key inside a JSON object */

static int find_key(int object_token, const char *key) {
    if (object_token < 0 ||
        object_token >= token_count ||
        tokens[object_token].type != TOKEN_OBJECT) {
        return -1;
    }

    int end = token_next(object_token);
    int child = object_token + 1;

    while (child < end) {
        int value = child + 1;

        if (value >= token_count) {
            return -1;
        }

        if (token_equals(child, key)) {
            return value;
        }

        child = token_next(value);
    }

    return -1;
}


/* Convert a JSON token to an integer */

static int token_integer(int token, int fallback) {
    if (token < 0 || token >= token_count) {
        return fallback;
    }

    if (token_equals(token, "null")) {
        return fallback;
    }

    char buffer[MAX_TEXT];

    token_string(token, buffer, sizeof(buffer));

    char *end = NULL;
    long value = strtol(buffer, &end, 10);

    if (end == buffer || *end != '\0') {
        return fallback;
    }

    return (int)value;
}


/* Convert HH:MM into minutes */

static int time_to_minutes(const char *value) {
    int hours = -1;
    int minutes = -1;
    char extra;

    if (sscanf(value, "%d:%d%c",
               &hours, &minutes, &extra) != 2) {
        return -1;
    }

    if (hours < 0 || hours > 23 ||
        minutes < 0 || minutes > 59) {
        return -1;
    }

    return hours * 60 + minutes;
}


/* Check whether two time intervals overlap */

static int intervals_overlap(const char *start1,
                             const char *end1,
                             const char *start2,
                             const char *end2) {
    int s1 = time_to_minutes(start1);
    int e1 = time_to_minutes(end1);
    int s2 = time_to_minutes(start2);
    int e2 = time_to_minutes(end2);

    if (s1 < 0 || e1 < 0 ||
        s2 < 0 || e2 < 0) {
        return 0;
    }

    return s1 < e2 && s2 < e1;
}


/* Find a classroom by its ID */

static int find_room(const char *room_id) {
    for (int i = 0; i < room_count; i++) {
        if (strcmp(rooms[i].id, room_id) == 0) {
            return i;
        }
    }

    return -1;
}


/* Determine which existing booking statuses block a room */

static int is_active_status(const char *status) {
    return strcmp(status, "ALLOCATED") == 0 ||
           strcmp(status, "APPROVED") == 0 ||
           strcmp(status, "CONFIRMED") == 0;
}


/* Load classrooms from JSON */

static int load_rooms(int array_token) {
    room_count = 0;

    if (array_token < 0 ||
        tokens[array_token].type != TOKEN_ARRAY) {
        return 0;
    }

    int end = token_next(array_token);
    int child = array_token + 1;

    while (child < end && room_count < MAX_ROOMS) {
        if (tokens[child].type != TOKEN_OBJECT) {
            child = token_next(child);
            continue;
        }

        Room *room = &rooms[room_count];

        memset(room, 0, sizeof(*room));

        token_string(find_key(child, "id"),
                     room->id, sizeof(room->id));

        token_string(find_key(child, "name"),
                     room->name, sizeof(room->name));

        room->capacity =
            token_integer(find_key(child, "capacity"), 0);

        room->active = 1;

        int status_token = find_key(child, "status");

        if (status_token >= 0) {
            char status[MAX_TEXT];

            token_string(status_token, status, sizeof(status));

            if (strcmp(status, "MAINTENANCE") == 0 ||
                strcmp(status, "INACTIVE") == 0) {
                room->active = 0;
            }
        }

        if (room->id[0] != '\0') {
            room_count++;
        }

        child = token_next(child);
    }

    return room_count;
}


/* Load existing bookings from JSON */

static int load_bookings(int array_token) {
    booking_count = 0;

    if (array_token < 0 ||
        tokens[array_token].type != TOKEN_ARRAY) {
        return 0;
    }

    int end = token_next(array_token);
    int child = array_token + 1;

    while (child < end && booking_count < MAX_BOOKINGS) {
        if (tokens[child].type != TOKEN_OBJECT) {
            child = token_next(child);
            continue;
        }

        Booking *booking = &bookings[booking_count];

        memset(booking, 0, sizeof(*booking));

        token_string(find_key(child, "id"),
                     booking->id, sizeof(booking->id));

        int faculty_token = find_key(child, "faculty");

        if (faculty_token < 0) {
            faculty_token = find_key(child, "faculty_name");
        }

        token_string(faculty_token,
                     booking->faculty, sizeof(booking->faculty));

        token_string(find_key(child, "room"),
                     booking->room, sizeof(booking->room));

        token_string(find_key(child, "day"),
                     booking->day, sizeof(booking->day));

        token_string(find_key(child, "start"),
                     booking->start, sizeof(booking->start));

        token_string(find_key(child, "end"),
                     booking->end, sizeof(booking->end));

        token_string(find_key(child, "status"),
                     booking->status, sizeof(booking->status));

        booking->students =
            token_integer(find_key(child, "students"), 1);

        booking->priority =
            token_integer(find_key(child, "priority"), 5);

        booking->processing_time =
            token_integer(find_key(child, "processing_time"), 1);

        if (booking->id[0] != '\0') {
            booking_count++;
        }

        child = token_next(child);
    }

    return booking_count;
}


/* Load pending booking requests in the supplied order */

static int load_pending(int array_token,
                        Booking *pending,
                        int max_pending) {
    int count = 0;

    if (array_token < 0 ||
        tokens[array_token].type != TOKEN_ARRAY) {
        return 0;
    }

    int end = token_next(array_token);
    int child = array_token + 1;

    while (child < end && count < max_pending) {
        if (tokens[child].type != TOKEN_OBJECT) {
            child = token_next(child);
            continue;
        }

        Booking *booking = &pending[count];

        memset(booking, 0, sizeof(*booking));

        token_string(find_key(child, "id"),
                     booking->id, sizeof(booking->id));

        int faculty_token = find_key(child, "faculty");

        if (faculty_token < 0) {
            faculty_token = find_key(child, "faculty_name");
        }

        token_string(faculty_token,
                     booking->faculty, sizeof(booking->faculty));

        token_string(find_key(child, "room"),
                     booking->room, sizeof(booking->room));

        token_string(find_key(child, "day"),
                     booking->day, sizeof(booking->day));

        token_string(find_key(child, "start"),
                     booking->start, sizeof(booking->start));

        token_string(find_key(child, "end"),
                     booking->end, sizeof(booking->end));

        booking->students =
            token_integer(find_key(child, "students"), 1);

        booking->priority =
            token_integer(find_key(child, "priority"), 5);

        booking->processing_time =
            token_integer(find_key(child, "processing_time"), 1);

        if (booking->processing_time <= 0) {
            int start = time_to_minutes(booking->start);
            int finish = time_to_minutes(booking->end);

            booking->processing_time =
                (start >= 0 && finish > start)
                    ? finish - start
                    : 1;
        }

        if (booking->id[0] != '\0') {
            count++;
        }

        child = token_next(child);
    }

    return count;
}


/* Check classroom availability */

static int is_room_available(const char *room_id,
                             const char *day,
                             const char *start,
                             const char *end,
                             int students,
                             char *reason,
                             size_t reason_size) {
    int room_index = find_room(room_id);

    if (room_index < 0) {
        snprintf(reason, reason_size, "ROOM_NOT_FOUND");
        return 0;
    }

    Room *room = &rooms[room_index];

    if (!room->active) {
        snprintf(reason, reason_size, "ROOM_UNAVAILABLE");
        return 0;
    }

    if (students <= 0) {
        snprintf(reason, reason_size, "INVALID_CAPACITY");
        return 0;
    }

    if (students > room->capacity) {
        snprintf(reason, reason_size, "CAPACITY_EXCEEDED");
        return 0;
    }

    int start_minutes = time_to_minutes(start);
    int end_minutes = time_to_minutes(end);

    if (start_minutes < 0 ||
        end_minutes < 0 ||
        end_minutes <= start_minutes) {
        snprintf(reason, reason_size, "INVALID_TIME");
        return 0;
    }

    for (int i = 0; i < booking_count; i++) {
        Booking *booking = &bookings[i];

        if (!is_active_status(booking->status)) {
            continue;
        }

        if (strcmp(booking->room, room_id) != 0) {
            continue;
        }

        if (strcmp(booking->day, day) != 0) {
            continue;
        }

        if (intervals_overlap(start, end,
                              booking->start, booking->end)) {
            snprintf(reason, reason_size, "TIME_CONFLICT");
            return 0;
        }
    }

    snprintf(reason, reason_size, "AVAILABLE");

    return 1;
}


/* Print a JSON-escaped string */

static void print_json_string(const char *value) {
    putchar('"');

    for (const unsigned char *p = (const unsigned char *)value;
         *p; p++) {
        switch (*p) {
            case '"':
                printf("\\\"");
                break;

            case '\\':
                printf("\\\\");
                break;

            case '\n':
                printf("\\n");
                break;

            case '\r':
                printf("\\r");
                break;

            case '\t':
                printf("\\t");
                break;

            default:
                if (*p < 32) {
                    printf("\\u%04x", *p);
                } else {
                    putchar(*p);
                }
        }
    }

    putchar('"');
}


/* Check one classroom request */

static void operation_check_room(int root) {
    char room_id[MAX_TEXT] = "";
    char day[MAX_TEXT] = "";
    char start[MAX_TEXT] = "";
    char end[MAX_TEXT] = "";
    char reason[MAX_TEXT] = "";

    token_string(find_key(root, "room"),
                 room_id, sizeof(room_id));

    token_string(find_key(root, "day"),
                 day, sizeof(day));

    token_string(find_key(root, "start"),
                 start, sizeof(start));

    token_string(find_key(root, "end"),
                 end, sizeof(end));

    int students = token_integer(
        find_key(root, "students"), 1
    );

    if (students <= 0) {
        students = token_integer(
            find_key(root, "required_capacity"), 1
        );
    }

    int available = is_room_available(
        room_id,
        day,
        start,
        end,
        students,
        reason,
        sizeof(reason)
    );

    int room_index = find_room(room_id);
    int room_found = room_index >= 0;

    int capacity_ok = room_found &&
                      students > 0 &&
                      students <= rooms[room_index].capacity;

    printf("{\"success\":true,\"available\":%s,"
           "\"capacity_ok\":%s,\"room_found\":%s,"
           "\"conflicts\":[],\"alternatives\":[",
           available ? "true" : "false",
           capacity_ok ? "true" : "false",
           room_found ? "true" : "false");

    int first = 1;

    if (!available && students > 0) {
        for (int i = 0; i < room_count; i++) {
            char alternative_reason[MAX_TEXT];

            if (!rooms[i].active ||
                rooms[i].capacity < students) {
                continue;
            }

            if (is_room_available(
                    rooms[i].id,
                    day,
                    start,
                    end,
                    students,
                    alternative_reason,
                    sizeof(alternative_reason))) {

                if (!first) {
                    putchar(',');
                }

                printf("{\"id\":");
                print_json_string(rooms[i].id);

                printf(",\"name\":");
                print_json_string(rooms[i].name);

                putchar('}');

                first = 0;
            }
        }
    }

    printf("],\"message\":");
    print_json_string(reason);
    printf("}\n");
}


/* Calculate booking duration */

static int booking_duration(const Booking *booking) {
    int start = time_to_minutes(booking->start);
    int end = time_to_minutes(booking->end);

    if (start < 0 || end <= start) {
        return booking->processing_time > 0
            ? booking->processing_time
            : 1;
    }

    return end - start;
}


/* Suggest alternative classrooms */

static void print_alternatives(const Booking *booking) {
    printf("[");

    int first = 1;

    for (int i = 0; i < room_count; i++) {
        char reason[MAX_TEXT];

        if (!rooms[i].active ||
            rooms[i].capacity < booking->students) {
            continue;
        }

        if (is_room_available(
                rooms[i].id,
                booking->day,
                booking->start,
                booking->end,
                booking->students,
                reason,
                sizeof(reason))) {

            if (!first) {
                putchar(',');
            }

            printf("{\"id\":");
            print_json_string(rooms[i].id);

            printf(",\"name\":");
            print_json_string(rooms[i].name);

            putchar('}');

            first = 0;
        }
    }

    printf("]");
}


/* Print each scheduling result.
   The day field is required by the Python application. */

static void print_booking_result(const Booking *booking,
                                 const char *result_status,
                                 const char *reason) {
    printf("{\"id\":");
    print_json_string(booking->id);

    printf(",\"day\":");
    print_json_string(booking->day);

    printf(",\"status\":");
    print_json_string(result_status);

    printf(",\"reason\":");
    print_json_string(reason);

    printf(",\"waiting_time\":%d", booking->waiting_time);

    printf(",\"turnaround_time\":%d",
           booking->turnaround_time);

    printf(",\"alternatives\":");
    print_alternatives(booking);

    printf("}");
}


/* FCFS scheduler */

static void operation_schedule(int root) {
    const char *algorithm = "FCFS";

    int pending_token = find_key(root, "pending");

    if (pending_token < 0) {
        pending_token = find_key(root, "requests");
    }

    /*
     * Static storage avoids placing a very large Booking array
     * on the stack.
     */
    static Booking pending[MAX_BOOKINGS];
    static Job jobs[MAX_BOOKINGS];

    int pending_count = load_pending(
        pending_token,
        pending,
        MAX_BOOKINGS
    );

    /*
     * FCFS means First Come, First Served.
     *
     * The Python application must send requests in ascending
     * request_id order. This C module preserves that order.
     */
    for (int i = 0; i < pending_count; i++) {
        jobs[i].index = i;
        jobs[i].priority = pending[i].priority;
        jobs[i].duration = booking_duration(&pending[i]);
        jobs[i].original_order = i;
    }

    printf("{\"success\":true,\"algorithm\":");
    print_json_string(algorithm);

    printf(",\"results\":[");

    int first_result = 1;
    int current_wait = 0;
    for (int i = 0; i < pending_count; i++) {
        Booking *booking = &pending[jobs[i].index];
        char reason[MAX_TEXT] = "";
        int available = is_room_available(
            booking->room,
            booking->day,
            booking->start,
            booking->end,
            booking->students,
            reason,
            sizeof(reason)
        );

        if (available) {
            strcpy(booking->status, "ALLOCATED");

            booking->waiting_time = current_wait;

            booking->turnaround_time =
                current_wait + booking_duration(booking);

            if (booking_count < MAX_BOOKINGS) {
                bookings[booking_count++] = *booking;
            }
        } else {
            strcpy(booking->status, "REJECTED");

            booking->waiting_time = 0;
            booking->turnaround_time = 0;
        }
        if (!first_result) {
            putchar(',');
        }
        print_booking_result(
            booking,
            booking->status,
            reason
        );
        first_result = 0;

        if (available) {
            current_wait += booking_duration(booking);
        }
    }
    printf("]}\n");
}
int main(void) {
    if (fgets(json, sizeof(json), stdin) == NULL) {
        printf("{\"success\":false,\"message\":\"NO_INPUT\"}\n");
        return 1;
    }
    if (strlen(json) >= sizeof(json) - 1 &&
        json[sizeof(json) - 2] != '\n') {
        printf("{\"success\":false,\"message\":\"INPUT_TOO_LARGE\"}\n");
        return 1;
    }
    int root = parse_json();
    if (root < 0) {
        printf("{\"success\":false,\"message\":\"INVALID_JSON\"}\n");
        return 1;
    }
    int operation_token = find_key(root, "operation");

    if (operation_token < 0) {
        printf("{\"success\":false,\"message\":\"MISSING_OPERATION\"}\n");
        return 1;
    }
    char operation[MAX_TEXT];

    token_string(
        operation_token,
        operation,
        sizeof(operation)
    );

    pthread_mutex_lock(&mutex);

    load_rooms(find_key(root, "rooms"));
    load_bookings(find_key(root, "bookings"));

    if (strcmp(operation, "check_room") == 0) {
        operation_check_room(root);
    } else if (strcmp(operation, "schedule") == 0) {
        operation_schedule(root);
    } else {
        printf("{\"success\":false,\"message\":\"UNKNOWN_OPERATION\"}\n");
    }

    pthread_mutex_unlock(&mutex);

    return 0;
}