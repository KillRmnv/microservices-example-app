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
import java.util.Optional;

@Repository
public interface TicketRepository extends JpaRepository<Ticket, Long>, JpaSpecificationExecutor<Ticket> {

    /**
     * Locks the {@code tickets} row that carries the mutable state
     * ({@code active}, {@code user_id}).
     *
     * <p>Native on purpose. A JPA {@code PESSIMISTIC_WRITE} lock on
     * {@code Ticket} or on the joined {@code SeatableTicket} subtype cannot be
     * inlined into the select, because resolving the concrete type of the
     * JOINED hierarchy already needs a join. Hibernate then falls back to
     * follow-on locking: a second locking statement driven by a query plan
     * that is cached and shared between threads. Concurrent refunds of one
     * ticket mutate that shared plan state, which either throws
     * {@link java.util.ConcurrentModificationException} out of the lock
     * acquisition or silently loses the lock and refunds the ticket twice.
     * A native {@code FOR NO KEY UPDATE} locks the row in one statement and
     * has no shared execution state.
     */
    @Query(value = "select id from tickets where id = :id for no key update",
            nativeQuery = true)
    Optional<Long> lockById(@Param("id") Long id);

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