package com.microservices_example_app.booking.repository;

import com.microservices_example_app.booking.model.Event;
import com.microservices_example_app.booking.model.EventAdmissionMode;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.JpaSpecificationExecutor;

import java.time.LocalDateTime;
import java.util.List;

public interface EventRepository extends JpaRepository<Event, Integer>, JpaSpecificationExecutor<Event> {
    List<Event> findByTitleContainingIgnoreCase(String title);
    List<Event> findByVenueId(Integer venueId);
    List<Event> findByAdmissionMode(EventAdmissionMode admissionMode);
    List<Event> findByStartsAtBetween(LocalDateTime from, LocalDateTime to);
}