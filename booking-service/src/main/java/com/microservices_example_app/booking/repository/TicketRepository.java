package com.microservices_example_app.booking.repository;

import com.microservices_example_app.booking.model.Ticket;
import com.microservices_example_app.booking.model.Zone;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.JpaSpecificationExecutor;
import org.springframework.stereotype.Repository;

import java.math.BigDecimal;
import java.util.List;
@Repository
public interface TicketRepository extends JpaRepository<Ticket, Integer>, JpaSpecificationExecutor<Ticket> {
    List<Ticket> findByEventId(Integer eventId);
    List<Ticket> findByUserId(Integer userId);
    List<Ticket> findByActive(boolean active);
    List<Ticket> findByEventIdAndZone(Integer eventId, Zone zone);
    List<Ticket> findByEventIdAndPriceLessThanEqual(Integer eventId, BigDecimal price);
}