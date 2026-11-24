CC ?= cc
CFLAGS ?= -Wall -Wextra -Werror -O2 -std=c11 -D_POSIX_C_SOURCE=200809L
LDFLAGS ?= -pthread

all: campusresos_worker

campusresos_worker: src/worker.c
	$(CC) $(CFLAGS) -o $@ $< $(LDFLAGS)

clean:
	rm -f campusresos_worker
.PHONY: all clean
