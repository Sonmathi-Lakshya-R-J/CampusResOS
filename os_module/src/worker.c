
#define _POSIX_C_SOURCE 200809L
#include <sys/socket.h>
#include <sys/un.h>
#include <sys/types.h>
#include <pthread.h>
#include <unistd.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <errno.h>
#include <signal.h>
#include <sys/stat.h>
#include <limits.h>


//edit: Added semaphore header for limiting concurrent clients
#include <semaphore.h>


#define SOCKET_PATH "/tmp/campusresos.sock"
#define BUF_SIZE 8192
#define MAX_JOBS 64

typedef struct { int fd; } client_arg;

typedef struct {
    int arrival, burst, priority, id;
    int start, finish, waiting, turnaround, done;
} job;

static pthread_mutex_t stats_mutex = PTHREAD_MUTEX_INITIALIZER;
static unsigned long requests_handled = 0;


//edit : Added semaphore to limit concurrent clients
static sem_t client_slots;



static void schedule_reply(const char *algorithm, const char *payload, char *out, size_t out_size) {
    job jobs[MAX_JOBS];
    int n = 0;
    char copy[4096];
    snprintf(copy, sizeof(copy), "%s", payload);
    char *save = NULL;
    for (char *item = strtok_r(copy, ";", &save); item && n < MAX_JOBS; item = strtok_r(NULL, ";", &save)) {
        int a, b, p;
        if (sscanf(item, "%d,%d,%d", &a, &b, &p) != 3 || a < 0 || b <= 0 || p < 0) continue;
        jobs[n] = (job){.arrival=a,.burst=b,.priority=p,.id=n,.done=0};
        n++;
    }
    if (!n) { snprintf(out, out_size, "ERROR|no-valid-jobs"); return; }

    int now = 0, completed = 0, total_wait = 0, total_turn = 0;
    while (completed < n) {
        int chosen = -1;
        for (int i = 0; i < n; i++) {
            if (jobs[i].done || jobs[i].arrival > now) continue;
            if (chosen < 0) chosen = i;
            else if (!strcmp(algorithm, "SJF")) {
                if (jobs[i].burst < jobs[chosen].burst ||
                    (jobs[i].burst == jobs[chosen].burst && jobs[i].arrival < jobs[chosen].arrival)) chosen = i;
            } else if (!strcmp(algorithm, "PRIORITY")) {
                if (jobs[i].priority < jobs[chosen].priority ||
                    (jobs[i].priority == jobs[chosen].priority && jobs[i].arrival < jobs[chosen].arrival)) chosen = i;
            } else if (jobs[i].arrival < jobs[chosen].arrival ||
                       (jobs[i].arrival == jobs[chosen].arrival && jobs[i].id < jobs[chosen].id)) chosen = i;
        }
        if (chosen < 0) {
            int next = INT_MAX;
            for (int i = 0; i < n; i++) if (!jobs[i].done && jobs[i].arrival < next) next = jobs[i].arrival;
            now = next;
            continue;
        }
        jobs[chosen].start = now;
        jobs[chosen].finish = now + jobs[chosen].burst;
        jobs[chosen].waiting = jobs[chosen].start - jobs[chosen].arrival;
        jobs[chosen].turnaround = jobs[chosen].finish - jobs[chosen].arrival;
        now = jobs[chosen].finish;
        jobs[chosen].done = 1;
        completed++;
        total_wait += jobs[chosen].waiting;
        total_turn += jobs[chosen].turnaround;
    }

    char lines[4096] = "";
    size_t used = 0;
    for (int i = 0; i < n; i++) {
        char line[128];
        snprintf(line, sizeof(line), "P%d(start=%d,finish=%d,wait=%d,turnaround=%d)%s",
                 jobs[i].id + 1, jobs[i].start, jobs[i].finish, jobs[i].waiting, jobs[i].turnaround,
                 i == n - 1 ? "" : ";");
        size_t len = strlen(line);
        if (used + len + 1 < sizeof(lines)) { memcpy(lines + used, line, len + 1); used += len; }
    }
    snprintf(out, out_size,
        "OK|algorithm=%.8s|jobs=%d|avg_wait=%.2f|avg_turnaround=%.2f|throughput=%.3f_jobs_per_unit|%.4000s",
        algorithm, n, (double)total_wait/n, (double)total_turn/n, now > 0 ? (double)n/now : 0.0, lines);
}








/*
 * CHECK command protocol:
 * CHECK|date,available,reason;date,available,reason;...
 * The Flask layer must query MySQL and pass each occurrence's availability
 * and reason. This worker validates/aggregates those results; it does not
 * connect to MySQL and must not be treated as the source of database truth.
 * available is 1 for available and 0 for unavailable. Use "-" for no reason.
 * Example: CHECK|2026-11-04,1,-;2026-11-11,0,Booked
 */
static void check_reply(const char *payload, char *out, size_t out_size) {
    char copy[4096];
    snprintf(copy, sizeof(copy), "%s", payload);
    char *save = NULL;
    int total = 0, available = 0, unavailable = 0;
    char details[3500] = "";
    size_t used = 0;

    for (char *item = strtok_r(copy, ";", &save); item && total < MAX_JOBS; item = strtok_r(NULL, ";", &save)) {
        char date[16] = {0}, reason[160] = {0};
        int ok = -1;
        if (sscanf(item, "%15[^,],%d,%159[^\n]", date, &ok, reason) < 2 ||
            strlen(date) != 10 || ok < 0 || ok > 1) continue;
        total++;
        if (ok) {
            available++;
        } else {
            unavailable++;
            char line[220];
            snprintf(line, sizeof(line), "%s:%s;", date, (reason[0] && strcmp(reason, "-")) ? reason : "Unavailable");
            size_t len = strlen(line);
            if (used + len + 1 < sizeof(details)) { memcpy(details + used, line, len + 1); used += len; }
        }
    }
    if (!total) { snprintf(out, out_size, "ERROR|no-valid-occurrences"); return; }
    snprintf(out, out_size, "OK|total=%d|available=%d|unavailable=%d|%s",
             total, available, unavailable, details);
}

static void *handle_client(void *arg) {
    client_arg *ca = (client_arg *)arg;
    int fd = ca->fd;
    free(ca);
    char buf[BUF_SIZE];
    size_t used = 0;
    while (used + 1 < sizeof(buf)) {
        char ch;
        ssize_t got = recv(fd, &ch, 1, 0);
        if (got <= 0 || ch == '\n') break;
        buf[used++] = ch;
    }
    buf[used] = '\0';

    char reply[BUF_SIZE];
    if (!strcmp(buf, "PING")) {
        pthread_mutex_lock(&stats_mutex);
        unsigned long count = ++requests_handled;
        pthread_mutex_unlock(&stats_mutex);
        snprintf(reply, sizeof(reply), "OK|PONG|requests=%lu\n", count);
    } else if (!strncmp(buf, "SCHEDULE|", 9)) {
        char copy[BUF_SIZE];
        snprintf(copy, sizeof(copy), "%s", buf + 9);
        char *sep = strchr(copy, '|');
        if (!sep) snprintf(reply, sizeof(reply), "ERROR|expected-algorithm-and-jobs\n");
        else {
            *sep = '\0';
            const char *algorithm = copy;
            if (strcmp(algorithm, "FCFS") && strcmp(algorithm, "SJF") && strcmp(algorithm, "PRIORITY"))
                snprintf(reply, sizeof(reply), "ERROR|unsupported-algorithm\n");
            else {
                schedule_reply(algorithm, sep + 1, reply, sizeof(reply) - 2);
                strncat(reply, "\n", sizeof(reply) - strlen(reply) - 1);
            }
        }
    } else if (!strncmp(buf, "CHECK|", 6)) {
        check_reply(buf + 6, reply, sizeof(reply) - 2);
        strncat(reply, "\n", sizeof(reply) - strlen(reply) - 1);
    } else {
        snprintf(reply, sizeof(reply), "ERROR|unknown-command\n");
    }
    (void)send(fd, reply, strlen(reply), 0);
    close(fd);


    // edit: Release the semaphore slot after handling the client
    sem_post(&client_slots);

    return NULL;
}

/*
int main(void) {
    signal(SIGPIPE, SIG_IGN);
    int server_fd = socket(AF_UNIX, SOCK_STREAM, 0);
    if (server_fd < 0) { perror("socket"); return 1; }

    struct sockaddr_un addr;
    memset(&addr, 0, sizeof(addr));
    addr.sun_family = AF_UNIX;
    snprintf(addr.sun_path, sizeof(addr.sun_path), "%s", SOCKET_PATH);
    unlink(SOCKET_PATH);
    if (bind(server_fd, (struct sockaddr *)&addr, sizeof(addr)) < 0) {
        perror("bind"); close(server_fd); return 1;
    }
    if (chmod(SOCKET_PATH, 0600) < 0) perror("chmod");
    if (listen(server_fd, 32) < 0) {
        perror("listen"); close(server_fd); unlink(SOCKET_PATH); return 1;
    }
    printf("CampusResOS C/POSIX worker listening on %s\n", SOCKET_PATH);
    fflush(stdout);

// edit: Added semaphore initialization to limit concurrent clients

    if (sem_init(&client_slots, 0, 5) != 0) {
        perror("sem_init");
        close(server_fd);
        unlink(SOCKET_PATH);
        return 1;
    }





    for (;;) {
        int client_fd = accept(server_fd, NULL, 0);

        // edit: Wait for a slot in the semaphore before proceeding to handle the client

        while (sem_wait(&client_slots) == -1) {
            if (errno == EINTR) continue;

            perror("sem_wait");
            close(client_fd);
            client_fd = -1;
            break;
        }

        if (client_fd < 0) continue;



        client_arg *arg = malloc(sizeof(*arg));

if (!arg) {
    close(client_fd);
    sem_post(&client_slots);
    continue;
}


if (pthread_create(&thread, NULL, handle_client, arg) != 0) {
    close(client_fd);
    free(arg);
    sem_post(&client_slots);
    continue;
}




        if (client_fd < 0) { if (errno == EINTR) continue; perror("accept"); continue; }
        client_arg *arg = malloc(sizeof(*arg));
        if (!arg) { close(client_fd); continue; }
        arg->fd = client_fd;
        pthread_t thread;
        if (pthread_create(&thread, NULL, handle_client, arg) != 0) { close(client_fd); free(arg); continue; }
        pthread_detach(thread);
    }
    close(server_fd);
    unlink(SOCKET_PATH);
    return 0;
}
*/


int main(void) {

    signal(SIGPIPE, SIG_IGN);

    int server_fd = socket(AF_UNIX, SOCK_STREAM, 0);
    if (server_fd < 0) {
        perror("socket");
        return 1;
    }

    struct sockaddr_un addr;
    memset(&addr, 0, sizeof(addr));

    addr.sun_family = AF_UNIX;
    snprintf(addr.sun_path, sizeof(addr.sun_path), "%s", SOCKET_PATH);

    unlink(SOCKET_PATH);

    if (bind(server_fd, (struct sockaddr *)&addr, sizeof(addr)) < 0) {
        perror("bind");
        close(server_fd);
        return 1;
    }

    if (chmod(SOCKET_PATH, 0600) < 0)
        perror("chmod");

    if (listen(server_fd, 32) < 0) {
        perror("listen");
        close(server_fd);
        unlink(SOCKET_PATH);
        return 1;
    }

    // Initialize semaphore with 5 permits
    if (sem_init(&client_slots, 0, 5) != 0) {
        perror("sem_init");
        close(server_fd);
        unlink(SOCKET_PATH);
        return 1;
    }

    printf("CampusResOS C/POSIX worker listening on %s\n",
           SOCKET_PATH);
    fflush(stdout);

    for (;;) {

        int client_fd = accept(server_fd, NULL, 0);

        if (client_fd < 0) {
            if (errno == EINTR)
                continue;

            perror("accept");
            continue;
        }

        // Acquire one semaphore permit
        while (sem_wait(&client_slots) == -1) {
            if (errno == EINTR)
                continue;

            perror("sem_wait");
            close(client_fd);
            client_fd = -1;
            break;
        }

        if (client_fd < 0)
            continue;

        client_arg *arg = malloc(sizeof(*arg));

        if (!arg) {
            close(client_fd);
            sem_post(&client_slots);
            continue;
        }

        arg->fd = client_fd;

        pthread_t thread;

        if (pthread_create(&thread, NULL, handle_client, arg) != 0) {
            close(client_fd);
            free(arg);
            sem_post(&client_slots);
            continue;
        }

        pthread_detach(thread);
    }

    return 0;
}
