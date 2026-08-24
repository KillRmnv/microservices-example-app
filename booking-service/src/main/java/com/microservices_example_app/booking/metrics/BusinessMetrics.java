package com.microservices_example_app.booking.metrics;

import io.micrometer.core.instrument.Counter;
import io.micrometer.core.instrument.MeterRegistry;
import io.micrometer.core.instrument.Timer;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Component;

@Component
@RequiredArgsConstructor
public class BusinessMetrics {

    private final MeterRegistry meterRegistry;

    public void recordTicketCreated() {
        Counter.builder("business.tickets.created")
                .description("Total tickets created")
                .register(meterRegistry)
                .increment();
    }

    public void recordTicketRefunded() {
        Counter.builder("business.tickets.refunded")
                .description("Total tickets refunded")
                .register(meterRegistry)
                .increment();
    }

    public void recordEventCreated() {
        Counter.builder("business.events.created")
                .description("Total events created")
                .register(meterRegistry)
                .increment();
    }

    public void recordEventDeleted() {
        Counter.builder("business.events.deleted")
                .description("Total events deleted")
                .register(meterRegistry)
                .increment();
    }

    public void recordVenueCreated() {
        Counter.builder("business.venues.created")
                .description("Total venues created")
                .register(meterRegistry)
                .increment();
    }

    public void recordTownCreated() {
        Counter.builder("business.towns.created")
                .description("Total towns created")
                .register(meterRegistry)
                .increment();
    }

    public void recordSeatCreated() {
        Counter.builder("business.seats.created")
                .description("Total seats created")
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

    public Timer.Sample startBookingTimer() {
        return Timer.start(meterRegistry);
    }

    public void recordBookingDuration(Timer.Sample sample, String operation) {
        sample.stop(Timer.builder("business.booking.operation.duration")
                .description("Booking operation duration")
                .tag("operation", operation)
                .register(meterRegistry));
    }
}
