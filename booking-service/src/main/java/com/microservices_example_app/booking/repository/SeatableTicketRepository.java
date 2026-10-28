package com.microservices_example_app.booking.repository;

import com.microservices_example_app.booking.model.SeatableTicket;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.JpaSpecificationExecutor;
import org.springframework.stereotype.Repository;

import java.util.List;
import java.util.Optional;

@Repository
public interface SeatableTicketRepository extends JpaRepository<SeatableTicket, Long>, JpaSpecificationExecutor<SeatableTicket> {
    List<SeatableTicket> findByEventId(Long eventId);

    List<SeatableTicket> findBySeatId(Long seatId);

    Optional<SeatableTicket> findByEventIdAndSeatId(Long eventId, Long seatId);

    boolean existsByEventIdAndSeatId(Long eventId, Long seatId);
}