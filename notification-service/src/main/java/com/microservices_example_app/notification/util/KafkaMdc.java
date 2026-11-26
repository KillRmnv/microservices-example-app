package com.microservices_example_app.notification.util;

import org.slf4j.MDC;

import java.util.UUID;

/**
 * MDC handling for Kafka listeners. notification-service has no servlet container,
 * so there is no HTTP request filter; each consumed record gets a fresh
 * {@code requestId} that is cleared after handling.
 */
public final class KafkaMdc {

    private KafkaMdc() {
    }

    public static String begin() {
        String requestId = UUID.randomUUID().toString();
        MDC.put("requestId", requestId);
        return requestId;
    }

    public static void end() {
        MDC.clear();
    }
}
