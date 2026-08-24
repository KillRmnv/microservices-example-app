package com.microservices_example_app.users.metrics;

import io.micrometer.core.instrument.Counter;
import io.micrometer.core.instrument.MeterRegistry;
import io.micrometer.core.instrument.Timer;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Component;

@Component
@RequiredArgsConstructor
public class BusinessMetrics {

    private final MeterRegistry meterRegistry;

    public void recordUserRegistered() {
        Counter.builder("business.users.registered")
                .description("Total user registrations")
                .register(meterRegistry)
                .increment();
    }

    public void recordUserDeleted() {
        Counter.builder("business.users.deleted")
                .description("Total user deletions")
                .register(meterRegistry)
                .increment();
    }

    public void recordPasswordReset() {
        Counter.builder("business.users.password_resets")
                .description("Total password resets")
                .register(meterRegistry)
                .increment();
    }

    public void recordLoginSuccess() {
        Counter.builder("business.users.login_success")
                .description("Total successful logins")
                .register(meterRegistry)
                .increment();
    }

    public void recordLoginFailure() {
        Counter.builder("business.users.login_failure")
                .description("Total failed login attempts")
                .register(meterRegistry)
                .increment();
    }

    public void recordEmailSent(String type) {
        Counter.builder("business.emails.sent")
                .description("Total emails sent")
                .tag("type", type)
                .register(meterRegistry)
                .increment();
    }

    public void recordKafkaEventSent(String topic) {
        Counter.builder("business.kafka.events.sent")
                .description("Total Kafka events sent")
                .tag("topic", topic)
                .register(meterRegistry)
                .increment();
    }

    public Timer.Sample startTimer() {
        return Timer.start(meterRegistry);
    }

    public void recordDuration(Timer.Sample sample, String operation) {
        sample.stop(Timer.builder("business.operation.duration")
                .description("Operation duration")
                .tag("operation", operation)
                .register(meterRegistry));
    }
}
