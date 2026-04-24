package com.microservices_example_app.booking.specification;

import com.microservices_example_app.booking.model.Ticket;
import com.microservices_example_app.booking.model.Zone;
import jakarta.persistence.criteria.CriteriaBuilder;
import jakarta.persistence.criteria.CriteriaQuery;
import jakarta.persistence.criteria.Predicate;
import jakarta.persistence.criteria.Root;
import org.jspecify.annotations.Nullable;
import org.springframework.data.jpa.domain.Specification;

import java.math.BigDecimal;

public class TicketSpecification {

    public static Specification<Ticket> hasEventId(Integer eventId) {
        return new Specification<Ticket>() {
            @Override
            public @Nullable Predicate toPredicate(Root<Ticket> root, CriteriaQuery<?> query, CriteriaBuilder criteriaBuilder) {
                if (eventId != null)
                    return criteriaBuilder.equal(root.get("event").get("id"), eventId);
                return null;
            }
        };
    }

    public static Specification<Ticket> hasZone(Zone zone) {
        return new Specification<Ticket>() {
            @Override
            public @Nullable Predicate toPredicate(Root<Ticket> root, CriteriaQuery<?> query, CriteriaBuilder criteriaBuilder) {
                if (zone != null)
                    return criteriaBuilder.equal(root.get("zone"), zone);
                return null;
            }
        };
    }

    public static Specification<Ticket> hasActive(Boolean active) {
        return new Specification<Ticket>() {
            @Override
            public @Nullable Predicate toPredicate(Root<Ticket> root, CriteriaQuery<?> query, CriteriaBuilder criteriaBuilder) {
                if (active != null)
                    return criteriaBuilder.equal(root.get("active"), active);
                return null;
            }
        };
    }

    public static Specification<Ticket> hasUserId(Integer userId) {
        return new Specification<Ticket>() {
            @Override
            public @Nullable Predicate toPredicate(Root<Ticket> root, CriteriaQuery<?> query, CriteriaBuilder criteriaBuilder) {
                if (userId != null)
                    return criteriaBuilder.equal(root.get("userId"), userId);
                return null;
            }
        };
    }

    public static Specification<Ticket> hasPriceGreaterThanOrEqual(BigDecimal price) {
        return new Specification<Ticket>() {
            @Override
            public @Nullable Predicate toPredicate(Root<Ticket> root, CriteriaQuery<?> query, CriteriaBuilder criteriaBuilder) {
                if (price != null)
                    return criteriaBuilder.greaterThanOrEqualTo(root.get("price"), price);
                return null;
            }
        };
    }

    public static Specification<Ticket> hasPriceLessThanOrEqual(BigDecimal price) {
        return new Specification<Ticket>() {
            @Override
            public @Nullable Predicate toPredicate(Root<Ticket> root, CriteriaQuery<?> query, CriteriaBuilder criteriaBuilder) {
                if (price != null)
                    return criteriaBuilder.lessThanOrEqualTo(root.get("price"), price);
                return null;
            }
        };
    }
}