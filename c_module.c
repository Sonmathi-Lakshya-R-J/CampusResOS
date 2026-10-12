#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <strings.h>
#include <ctype.h>
#include <pthread.h>
#define MAX_TOKENS 30000
#define MAX_TEXT 256
#define MAX_BOOKINGS 2000
#define MAX_ROOMS 500
#define INPUT_SIZE (2 * 1024 * 1024)
typedef struct {
    int start, end, size, parent;
} Token;
typedef struct {
    char id[MAX_TEXT];
    char name[MAX_TEXT];
    int capacity;
} Room;
typedef struct {
    char id[MAX_TEXT];
    char faculty[MAX_TEXT];
    char room[MAX_TEXT];
    char day[MAX_TEXT];
    char start[MAX_TEXT];
    char end[MAX_TEXT];
    char course[MAX_TEXT];
    char type[MAX_TEXT];
    char status[MAX_TEXT];
    int students;
    int priority;
    int processing_time;
} Booking;
static Token tokens[MAX_TOKENS];
static int token_count;
static char input_buffer[INPUT_SIZE];
static Room rooms[MAX_ROOMS];
static int room_count;
static Booking bookings[MAX_BOOKINGS];
static int booking_count;
static pthread_mutex_t allocation_lock = PTHREAD_MUTEX_INITIALIZER;
static void skip_whitespace(int *p) {
    while (input_buffer[*p] &&
           isspace((unsigned char)input_buffer[*p])) {
        (*p)++;
    }
}
static int parse_value(int *p, int parent);
static int parse_string(int *p, int parent) {
    int index = ++(*p);
    int id = token_count++;
    if (id >= MAX_TOKENS)
        return -1;
    tokens[id].start = index;
    tokens[id].parent = parent;
    tokens[id].size = 0;
    while (input_buffer[*p]) {
        if (input_buffer[*p] == '\\' &&
            input_buffer[*p + 1]) {
            *p += 2;
            continue;
        }
        if (input_buffer[*p] == '"') {
            tokens[id].end = *p;
            (*p)++;
            return id;
        }
        (*p)++;
    }
    tokens[id].end = *p;
    return id;
}
static int parse_value(int *p, int parent) {
    skip_whitespace(p);
    if (!input_buffer[*p])
        return -1;
    int id = token_count++;
    if (id >= MAX_TOKENS)
        return -1;
    tokens[id].parent = parent;
    tokens[id].size = 0;
    tokens[id].start = *p;
    char c = input_buffer[*p];
    if (c == '"') {
        token_count--;
        return parse_string(p, parent);
    }
    if (c == '{' || c == '[') {
        (*p)++;
        skip_whitespace(p);
        while (input_buffer[*p] &&
               input_buffer[*p] != (c == '{' ? '}' : ']')) {
            if (input_buffer[*p] == ',' ||
                input_buffer[*p] == ':') {
                (*p)++;
                continue;
            }
            int child = parse_value(p, id);
            if (child < 0)
                return -1;
            tokens[id].size++;
            skip_whitespace(p);
        }

        if (input_buffer[*p])
            (*p)++;

        tokens[id].end = *p;
        return id;
    }
    while (input_buffer[*p] &&
           input_buffer[*p] != ',' &&
           input_buffer[*p] != ']' &&
           input_buffer[*p] != '}' &&
           !isspace((unsigned char)input_buffer[*p])) {
        (*p)++;
    }
    tokens[id].end = *p;
    return id;
}
static int next_token(int id) {
    int end = tokens[id].end;
    id++;
    while (id < token_count && tokens[id].start < end)
        id++;

    return id;
}
static int token_equals(int id, const char *value) {
    if (id < 0 || id >= token_count)
        return 0;
    int length = tokens[id].end - tokens[id].start;
    return length == (int)strlen(value) &&
           strncmp(input_buffer + tokens[id].start,
                   value, (size_t)length) == 0;
}
static void get_token_text(int id, char *output, size_t size) {
    if (size == 0)
        return;
    output[0] = '\0';
    if (id < 0 || id >= token_count)
        return;
    int length = tokens[id].end - tokens[id].start;
    if (length < 0)
        return;
    if ((size_t)length >= size)
        length = (int)size - 1;
    memcpy(output, input_buffer + tokens[id].start,
           (size_t)length);
    output[length] = '\0';
    if (tokens[id].start > 0 &&
        input_buffer[tokens[id].start - 1] == '"') {
        char temporary[MAX_TEXT * 2];
        size_t j = 0;
        for (size_t i = 0;
             output[i] && j + 1 < sizeof(temporary);
             i++) {
            if (output[i] == '\\' && output[i + 1]) {
                i++;
                if (output[i] == 'n' ||
                    output[i] == 't') {
                    temporary[j++] = ' ';
                } else {
                    temporary[j++] = output[i];
                }
            } else {
                temporary[j++] = output[i];
            }
        }
        temporary[j] = '\0';
        snprintf(output, size, "%s", temporary);
    }
}
static int object_get(int object, const char *key) {
    if (object < 0 || object >= token_count)
        return -1;
    int i = object + 1;
    while (i < token_count &&
           tokens[i].start < tokens[object].end) {
        int key_token = i;
        int value_token = key_token + 1;
        if (value_token >= token_count)
            return -1;
        if (token_equals(key_token, key))
            return value_token;
        i = next_token(value_token);
    }
    return -1;
}
static int array_item(int array, int wanted) {
    if (array < 0 || array >= token_count)
        return -1;
    int i = array + 1;
    int count = 0;
    while (i < token_count &&
           tokens[i].start < tokens[array].end) {
        if (count == wanted)
            return i;
        count++;
        i = next_token(i);
    }
    return -1;
}
static void get_string_field(
    int object,
    const char *key,
    char *output,
    size_t size,
    const char *fallback
) {
    int id = object_get(object, key);
    if (id < 0) {
        snprintf(output, size, "%s",
                 fallback ? fallback : "");
        return;
    }
    get_token_text(id, output, size);
}
static int get_integer_field(
    int object,
    const char *key,
    int fallback
) {
    int id = object_get(object, key);
    if (id < 0)
        return fallback;
    char value[64];
    get_token_text(id, value, sizeof(value));
    return atoi(value);
}
static int is_active(const Booking *b) {
    return strcmp(b->status, "ALLOCATED") == 0 ||
           strcmp(b->status, "APPROVED") == 0 ||
           strcmp(b->status, "CONFIRMED") == 0;
}
static int overlaps(
    const char *start1,
    const char *end1,
    const char *start2,
    const char *end2
) {
    return strcmp(start1, end2) < 0 &&
           strcmp(start2, end1) < 0;
}
static int same_room(const Booking *a, const Booking *b) {
    return strcmp(a->room, b->room) == 0;
}
static int same_day(const Booking *a, const Booking *b) {
    return strcasecmp(a->day, b->day) == 0;
}
static int has_conflict(const Booking *a, const Booking *b) {
    return same_room(a, b) &&
           same_day(a, b) &&
           overlaps(a->start, a->end, b->start, b->end);
}
static int find_room(const char *id_or_name) {
    for (int i = 0; i < room_count; i++) {
        if (strcmp(rooms[i].id, id_or_name) == 0 ||
            strcasecmp(rooms[i].name, id_or_name) == 0) {
            return i;
        }
    }
    return -1;
}
static int room_is_busy(
    const Booking *candidate,
    int skip_index
) {
    for (int i = 0; i < booking_count; i++) {
        if (i == skip_index)
            continue;
        if (!is_active(&bookings[i]))
            continue;
        if (has_conflict(candidate, &bookings[i]))
            return 1;
    }
    return 0;
}
static void load_data(int root) {
    room_count = 0;
    booking_count = 0;
    int room_array = object_get(root, "rooms");
    for (int i = 0; i < MAX_ROOMS; i++) {
        int item = array_item(room_array, i);
        if (item < 0)
            break;
        Room *r = &rooms[room_count++];
        get_string_field(item, "id",
                         r->id, sizeof(r->id), "");
        get_string_field(item, "name",
                         r->name, sizeof(r->name), r->id);
        r->capacity =
            get_integer_field(item, "capacity", 0);
    }
    int booking_array = object_get(root, "bookings");
    for (int i = 0; i < MAX_BOOKINGS; i++) {
        int item = array_item(booking_array, i);
        if (item < 0)
            break;
        Booking *b = &bookings[booking_count++];
        memset(b, 0, sizeof(*b));
        get_string_field(item, "id",
                         b->id, sizeof(b->id), "");
        get_string_field(item, "faculty",
                         b->faculty, sizeof(b->faculty), "");
        if (object_get(item, "faculty_name") >= 0) {
            get_string_field(item, "faculty_name",
                             b->faculty, sizeof(b->faculty), "");
        }
        get_string_field(item, "room",
                         b->room, sizeof(b->room), "");
        get_string_field(item, "day",
                         b->day, sizeof(b->day), "");
        get_string_field(item, "start",
                         b->start, sizeof(b->start), "");
        get_string_field(item, "end",
                         b->end, sizeof(b->end), "");
        get_string_field(item, "course",
                         b->course, sizeof(b->course), "");
        get_string_field(item, "type",
                         b->type, sizeof(b->type), "temporary");
        get_string_field(item, "status",
                         b->status, sizeof(b->status), "PENDING");
        b->students = get_integer_field(item, "students", 0);
        b->priority = get_integer_field(item, "priority", 1);
        b->processing_time =
            get_integer_field(item, "processing_time", 1);
    }
    for (int i = 0; i < booking_count; i++) {
        int r = find_room(bookings[i].room);

        if (r >= 0) {
            snprintf(bookings[i].room,
                     sizeof(bookings[i].room),
                     "%s", rooms[r].id);
        }
    }
}
static void print_json_string(const char *text) {
    putchar('"');

    for (const unsigned char *p =
             (const unsigned char *)text; *p; p++) {

        if (*p == '"' || *p == '\\')
            putchar('\\');

        if (*p == '\n' || *p == '\r')
            putchar(' ');
        else
            putchar(*p);
    }

    putchar('"');
}

static void print_alternatives(
    const Booking *candidate,
    int include_requested_room
) {
    int first = 1;

    printf("\"alternatives\":[");

    for (int r = 0; r < room_count; r++) {
        if (!include_requested_room &&
            strcmp(rooms[r].id, candidate->room) == 0) {
            continue;
        }

        if (rooms[r].capacity < candidate->students)
            continue;

        Booking test = *candidate;

        snprintf(test.room, sizeof(test.room),
                 "%s", rooms[r].id);

        if (room_is_busy(&test, -1))
            continue;

        if (!first)
            putchar(',');

        first = 0;

        printf("{\"id\":");
        print_json_string(rooms[r].id);

        printf(",\"name\":");
        print_json_string(rooms[r].name);

        printf(",\"capacity\":%d}", rooms[r].capacity);
    }

    printf("]");
}
static void operation_check_room(int root) {
    char room[MAX_TEXT];
    char day[MAX_TEXT];
    char start[MAX_TEXT];
    char end[MAX_TEXT];

    int students = get_integer_field(
        root, "students",
        get_integer_field(root, "required_capacity", 0)
    );

    get_string_field(root, "room",
                     room, sizeof(room), "");

    get_string_field(root, "day",
                     day, sizeof(day), "");

    get_string_field(root, "start",
                     start, sizeof(start), "");

    get_string_field(root, "end",
                     end, sizeof(end), "");
    int room_id = find_room(room);
    Booking query = {0};
    snprintf(query.room, sizeof(query.room), "%s",
             room_id >= 0 ? rooms[room_id].id : room);
    snprintf(query.day, sizeof(query.day), "%s", day);
    snprintf(query.start, sizeof(query.start), "%s", start);
    snprintf(query.end, sizeof(query.end), "%s", end);
    query.students = students;
     int valid = room_id >= 0 &&
                *day && *start && *end &&
                strcmp(start, end) < 0;
     int capacity_ok = room_id >= 0 &&
                      students > 0 &&
                      rooms[room_id].capacity >= students;
    pthread_mutex_lock(&allocation_lock);
    int available = valid &&
                    capacity_ok &&
                    !room_is_busy(&query, -1);
      printf("{\"success\":true,"
           "\"operation\":\"check_room\","
           "\"available\":%s,"
           "\"capacity_ok\":%s,"
           "\"room_found\":%s,"
           "\"conflicts\":[",
           available ? "true" : "false",
           capacity_ok ? "true" : "false",
           room_id >= 0 ? "true" : "false");
int first = 1;for (int i = 0; i < booking_count; i++) {
        if (is_active(&bookings[i]) &&
            has_conflict(&query, &bookings[i])) {

            if (!first)
                putchar(',');

            first = 0;

            printf("{\"booking_id\":");
            print_json_string(bookings[i].id);

            printf(",\"faculty\":");
            print_json_string(bookings[i].faculty);

            printf(",\"start\":");
            print_json_string(bookings[i].start);

            printf(",\"end\":");
            print_json_string(bookings[i].end);

            putchar('}');
        }
    }
    printf("],");
    print_alternatives(&query, 0);
    printf(",\"message\":");
    if (!valid) {
        print_json_string("Invalid room or time details.");
    } else if (!capacity_ok) {
        print_json_string("Room capacity is insufficient.");
    } else if (available) {
        print_json_string("Room is available.");
    } else {
        print_json_string("Room has a scheduling conflict.");
    }
    printf("}\n");
    pthread_mutex_unlock(&allocation_lock);
}
static int comes_before(
    const Booking *a,
    const Booking *b,
    const char *algorithm
) {
    if (strcmp(algorithm, "PRIORITY") == 0 &&
        a->priority != b->priority) {
        return a->priority > b->priority;
    }
    return atoi(a->id) < atoi(b->id);
}
static void operation_schedule(int root) {
    char algorithm[64];

    get_string_field(root, "algorithm",
                     algorithm, sizeof(algorithm), "FCFS");

    for (char *p = algorithm; *p; p++) {
        *p = (char)toupper((unsigned char)*p);
    }

    if (strcmp(algorithm, "FCFS") != 0 &&
        strcmp(algorithm, "PRIORITY") != 0) {

        printf("{\"success\":false,"
               "\"message\":\"Choose FCFS or PRIORITY.\"}\n");
        return;
    }
    int pending_array = object_get(root, "pending");
    Booking pending[MAX_BOOKINGS];
    int count = 0;
    for (int i = 0; i < MAX_BOOKINGS; i++) {
        int item = array_item(pending_array, i);
        if (item < 0)
            break;
        Booking *b = &pending[count++];
        memset(b, 0, sizeof(*b));
        get_string_field(item, "id",
                         b->id, sizeof(b->id), "");

        get_string_field(item, "faculty",
                         b->faculty, sizeof(b->faculty), "");

        get_string_field(item, "room",
                         b->room, sizeof(b->room), "");

        get_string_field(item, "day",
                         b->day, sizeof(b->day), "");

        get_string_field(item, "start",
                         b->start, sizeof(b->start), "");

        get_string_field(item, "end",
                         b->end, sizeof(b->end), "");

        get_string_field(item, "course",
                         b->course, sizeof(b->course), "");

        get_string_field(item, "type",
                         b->type, sizeof(b->type), "temporary");

        get_string_field(item, "status",
                         b->status, sizeof(b->status), "PENDING");

        b->students = get_integer_field(item, "students", 0);
        b->priority = get_integer_field(item, "priority", 1);

        b->processing_time =
            get_integer_field(item, "processing_time", 1);

        int r = find_room(b->room);

        if (r >= 0) {
            snprintf(b->room, sizeof(b->room),
                     "%s", rooms[r].id);
        }
    }
    for (int i = 0; i < count; i++) {
        for (int j = i + 1; j < count; j++) {
            if (comes_before(&pending[j], &pending[i], algorithm)) {
                Booking temp = pending[i];
                pending[i] = pending[j];
                pending[j] = temp;
            }
        }
    }

    printf("{\"success\":true,\"algorithm\":");
    print_json_string(algorithm);
    printf(",\"results\":[");

    int elapsed = 0;

    pthread_mutex_lock(&allocation_lock);

    for (int i = 0; i < count; i++) {
        Booking *b = &pending[i];

        char reason[256] = "";
        int room_id = find_room(b->room);
        int accepted = 1;

        if (!*b->id || !*b->faculty ||
            !*b->day || !*b->start || !*b->end ||
            strcmp(b->start, b->end) >= 0) {

            accepted = 0;
            snprintf(reason, sizeof(reason),
                     "Invalid or incomplete booking details.");

        } else if (b->students <= 0) {

            accepted = 0;
            snprintf(reason, sizeof(reason),
                     "Student count must be greater than zero.");

        } else if (room_id < 0) {

            accepted = 0;
            snprintf(reason, sizeof(reason),
                     "Requested room does not exist.");

        } else if (rooms[room_id].capacity < b->students) {

            accepted = 0;
            snprintf(reason, sizeof(reason),
                     "Room capacity is insufficient.");

        } else if (room_is_busy(b, -1)) {

            accepted = 0;
            snprintf(reason, sizeof(reason),
                     "Room has an overlapping booking.");
        }

        if (accepted) {
            snprintf(b->status, sizeof(b->status), "ALLOCATED");

            if (booking_count < MAX_BOOKINGS) {
                bookings[booking_count++] = *b;
            } else {
                accepted = 0;
                snprintf(b->status, sizeof(b->status), "REJECTED");
                snprintf(reason, sizeof(reason),
                         "Booking storage limit reached.");
            }
        } else {
            snprintf(b->status, sizeof(b->status), "REJECTED");
        }

        if (i)
            putchar(',');

        printf("{\"id\":");
        print_json_string(b->id);
        printf(",\"status\":");
        print_json_string(b->status);

        printf(",\"reason\":");
        print_json_string(reason);

        int processing = b->processing_time > 0
                         ? b->processing_time : 1;

        printf(",\"waiting_time\":%d", elapsed);
        printf(",\"turnaround_time\":%d", elapsed + processing);

        elapsed += processing;

        printf(",");
        print_alternatives(b, 0);
        putchar('}');
    }
    pthread_mutex_unlock(&allocation_lock);
    printf("]}\n");
}
static void *process_request(void *argument) {
    (void)argument;

    token_count = 0;
    int position = 0;
    int root = parse_value(&position, -1);
     if (root < 0 ||
        input_buffer[tokens[root].start] != '{') {

        printf("{\"success\":false,"
               "\"message\":\"Invalid JSON request.\"}\n");
        return NULL;
    }
    load_data(root);
    char operation[64];
     get_string_field(root, "operation",
                     operation, sizeof(operation), "");

    if (strcmp(operation, "check_room") == 0) {
        operation_check_room(root);
    } else if (strcmp(operation, "schedule") == 0) {
        operation_schedule(root);
    } else {
        printf("{\"success\":false,"
               "\"message\":\"Unknown operation. "
               "Use check_room or schedule.\"}\n");
    }

    return NULL;
}
int main(void) {
    if (!fgets(input_buffer, sizeof(input_buffer), stdin)) {
        puts("{\"success\":false,\"message\":\"No input received.\"}");
        return 1;
    }

    pthread_t thread;

    if (pthread_create(&thread, NULL,
                       process_request, NULL) != 0) {
        puts("{\"success\":false,"
             "\"message\":\"Unable to create POSIX thread.\"}");
        return 1;
    }

    pthread_join(thread, NULL);

    return 0;
}