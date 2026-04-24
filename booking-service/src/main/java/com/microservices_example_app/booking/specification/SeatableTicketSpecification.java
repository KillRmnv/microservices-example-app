package com.microservices_example_app.booking.specification;

import com.microservices_example_app.booking.model.SeatableTicket;
import com.microservices_example_app.booking.model.Zone;
import jakarta.persistence.criteria.CriteriaBuilder;
import jakarta.persistence.criteria.CriteriaQuery;
import jakarta.persistence.criteria.Predicate;
import jakarta.persistence.criteria.Root;
import org.jspecify.annotations.Nullable;
import org.springframework.data.jpa.domain.Specification;

import java.math.BigDecimal;

public class SeatableTicketSpecification {

    public static Specification<SeatableTicket> hasEventId(Integer eventId) {
        return new Specification<SeatableTicket>() {
            @Override
            public @Nullable Predicate toPredicate(Root<SeatableTicket> root, CriteriaQuery<?> query, CriteriaBuilder criteriaBuilder) {
                if (eventId != null)
                    return criteriaBuilder.equal(root.get("event").get("id"), eventId);
                return null;
            }
        };
    }

    public static Specification<SeatableTicket> hasSeatId(Integer seatId) {
        return new Specification<SeatableTicket>() {
            @Override
            public @Nullable Predicate toPredicate(Root<SeatableTicket> root, CriteriaQuery<?> query, CriteriaBuilder criteriaBuilder) {
                if (seatId != null)
                    return criteriaBuilder.equal(root.get("seat").get("id"), seatId);
                return null;
            }
        };
    }

    public static Specification<SeatableTicket> hasZone(Zone zone) {
        return new Specification<SeatableTicket>() {
            @Override
            public @Nullable Predicate toPredicate(Root<SeatableTicket> root, CriteriaQuery<?> query, CriteriaBuilder criteriaBuilder) {
                if (zone != null)
                    return criteriaBuilder.equal(root.get("zone"), zone);
                return null;
            }
        };
    }

    public static Specification<SeatableTicket> hasActive(Boolean active) {
        return new Specification<SeatableTicket>() {
            @Override
            public @Nullable Predicate toPredicate(Root<SeatableTicket> root, CriteriaQuery<?> query, CriteriaBuilder criteriaBuilder) {
                if (active != null)
                    return criteriaBuilder.equal(root.get("active"), active);
                return null;
            }
        };
    }

    public static Specification<SeatableTicket> hasUserId(Integer userId) {
        return new Specification<SeatableTicket>() {
            @Override
            public @Nullable Predicate toPredicate(Root<SeatableTicket> root, CriteriaQuery<?> query, CriteriaBuilder criteriaBuilder) {
                if (userId != null)
                    return criteriaBuilder.equal(root.get("userId"), userId);
                return null;
            }
        };
    }

    public static Specification<SeatableTicket> hasPriceGreaterThanOrEqual(BigDecimal price) {
        return new Specification<SeatableTicket>() {
            @Override
            public @Nullable Predicate toPredicate(Root<SeatableTicket> root, CriteriaQuery<?> query, CriteriaBuilder criteriaBuilder) {
                if (price != null)
                    return criteriaBuilder.greaterThanOrEqualTo(root.get("price"), price);
                return null;
            }
        };
    }

    public static Specification<SeatableTicket> hasPriceLessThanOrEqual(BigDecimal price) {
        return new Specification<SeatableTicket>() {
            @Override
            public @Nullable Predicate toPredicate(Root<SeatableTicket> root, CriteriaQuery<?> query, CriteriaBuilder criteriaBuilder) {
                if (price != null)
                    return criteriaBuilder.lessThanOrEqualTo(root.get("price"), price);
                return null;
            }
        };
    }

    public static Specification<SeatableTicket> hasSector(String sector) {
        return new Specification<SeatableTicket>() {
            @Override
            public @Nullable Predicate toPredicate(Root<SeatableTicket> root, CriteriaQuery<?> query, CriteriaBuilder criteriaBuilder) {
                if (sector != null && !sector.isBlank())
                    return criteriaBuilder.equal(criteriaBuilder.lower(root.get("seat").get("sector")), sector.toLowerCase());
                return null;
            }
        };
    }

    public static Specification<SeatableTicket> hasRow(String row) {
        return new Specification<SeatableTicket>() {
            @Override
            public @Nullable Predicate toPredicate(Root<SeatableTicket> root, CriteriaQuery<?> query, CriteriaBuilder criteriaBuilder) {
                if (row != null && !row.isBlank())
                    return criteriaBuilder.equal(criteriaBuilder.lower(root.get("seat").get("row")), row.toLowerCase());
                return null;
            }
        };
    }

    public static Specification<SeatableTicket> hasNumber(String number) {
        return new Specification<SeatableTicket>() {
            @Override
            public @Nullable Predicate toPredicate(Root<SeatableTicket> root, CriteriaQuery<?> query, CriteriaBuilder criteriaBuilder) {
                if (number != null && !number.isBlank())
                    return criteriaBuilder.equal(criteriaBuilder.lower(root.get("seat").get("number")), number.toLowerCase());
                return null;
            }
        };
    }
}