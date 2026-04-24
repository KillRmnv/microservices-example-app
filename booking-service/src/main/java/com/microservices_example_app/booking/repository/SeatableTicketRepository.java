package com.microservices_example_app.booking.repository;

import com.microservices_example_app.booking.model.SeatableTicket;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.JpaSpecificationExecutor;

import java.util.List;
import java.util.Optional;

public interface SeatableTicketRepository extends JpaRepository<SeatableTicket, Integer>, JpaSpecificationExecutor<SeatableTicket> {
    List<SeatableTicket> findByEventId(Integer eventId);
    List<SeatableTicket> findBySeatId(Integer seatId);
    Optional<SeatableTicket> findByEventIdAndSeatId(Integer eventId, Integer seatId);
    boolean existsByEventIdAndSeatId(Integer eventId, Integer seatId);
}