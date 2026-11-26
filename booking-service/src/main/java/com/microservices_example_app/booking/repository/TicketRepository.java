package com.microservices_example_app.booking.repository;

import com.microservices_example_app.booking.model.Ticket;
import com.microservices_example_app.booking.model.Zone;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.JpaSpecificationExecutor;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import org.springframework.stereotype.Repository;

import java.math.BigDecimal;
import java.util.Arrays;
import java.util.List;

@Repository
public interface TicketRepository extends JpaRepository<Ticket, Long>, JpaSpecificationExecutor<Ticket> {
    List<Ticket> findByEventId(Long eventId);

    List<Ticket> findByUserId(Long userId);

    List<Ticket> findByActive(boolean active);

    List<Ticket> findByEventIdAndZone(Long eventId, Zone zone);

    List<Ticket> findByEventIdAndPriceLessThanEqual(Long eventId, BigDecimal price);

    List<Ticket> findByEventIdInAndUserIdIsNotNull(List<Long> eventIds);

    List<Ticket> findByEventIdInAndUserIdIsNotNullOrderByIdDesc(List<Long> eventIds);

    List<Ticket> findByEventIdIn(List<Long> list);

    long countByEventIdAndActiveTrue(Long eventId);

    /**
     * Active tickets grouped by zone. Seatable tickets live in the same
     * {@code tickets} table (JOINED inheritance), so this single aggregate
     * already covers both general and seatable admissions.
     */
    @Query("""
            select t.zone as zone, count(t) as seatsLeft, min(t.price) as minPrice
            from Ticket t
            where t.event.id = :eventId and t.active = true
            group by t.zone
            """)
    List<ZoneAvailabilityProjection> aggregateActiveByZone(@Param("eventId") Long eventId);
}