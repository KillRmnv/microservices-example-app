package com.microservices_example_app.booking.specification;

import com.microservices_example_app.booking.model.Event;
import com.microservices_example_app.booking.model.EventAdmissionMode;
import jakarta.persistence.criteria.CriteriaBuilder;
import jakarta.persistence.criteria.CriteriaQuery;
import jakarta.persistence.criteria.Predicate;
import jakarta.persistence.criteria.Root;
import org.jspecify.annotations.Nullable;
import org.springframework.data.jpa.domain.Specification;

import java.time.LocalDateTime;

public class EventSpecification {

    public static Specification<Event> hasTitle(String title) {
        return new Specification<Event>() {
            @Override
            public @Nullable Predicate toPredicate(Root<Event> root, CriteriaQuery<?> query, CriteriaBuilder criteriaBuilder) {
                if (title != null && !title.isBlank())
                    return criteriaBuilder.like(criteriaBuilder.lower(root.get("title")), "%" + title.toLowerCase() + "%");
                return null;
            }
        };
    }

    public static Specification<Event> hasVenueId(Integer venueId) {
        return new Specification<Event>() {
            @Override
            public @Nullable Predicate toPredicate(Root<Event> root, CriteriaQuery<?> query, CriteriaBuilder criteriaBuilder) {
                if (venueId != null)
                    return criteriaBuilder.equal(root.get("venue").get("id"), venueId);
                return null;
            }
        };
    }

    public static Specification<Event> hasAdmissionMode(EventAdmissionMode admissionMode) {
        return new Specification<Event>() {
            @Override
            public @Nullable Predicate toPredicate(Root<Event> root, CriteriaQuery<?> query, CriteriaBuilder criteriaBuilder) {
                if (admissionMode != null)
                    return criteriaBuilder.equal(root.get("admissionMode"), admissionMode);
                return null;
            }
        };
    }

    public static Specification<Event> startsAfter(LocalDateTime startsAt) {
        return new Specification<Event>() {
            @Override
            public @Nullable Predicate toPredicate(Root<Event> root, CriteriaQuery<?> query, CriteriaBuilder criteriaBuilder) {
                if (startsAt != null)
                    return criteriaBuilder.greaterThanOrEqualTo(root.get("startsAt"), startsAt);
                return null;
            }
        };
    }

    public static Specification<Event> startsBefore(LocalDateTime startsAt) {
        return new Specification<Event>() {
            @Override
            public @Nullable Predicate toPredicate(Root<Event> root, CriteriaQuery<?> query, CriteriaBuilder criteriaBuilder) {
                if (startsAt != null)
                    return criteriaBuilder.lessThanOrEqualTo(root.get("startsAt"), startsAt);
                return null;
            }
        };
    }

    public static Specification<Event> endsAfter(LocalDateTime endsAt) {
        return new Specification<Event>() {
            @Override
            public @Nullable Predicate toPredicate(Root<Event> root, CriteriaQuery<?> query, CriteriaBuilder criteriaBuilder) {
                if (endsAt != null)
                    return criteriaBuilder.greaterThanOrEqualTo(root.get("endsAt"), endsAt);
                return null;
            }
        };
    }

    public static Specification<Event> endsBefore(LocalDateTime endsAt) {
        return new Specification<Event>() {
            @Override
            public @Nullable Predicate toPredicate(Root<Event> root, CriteriaQuery<?> query, CriteriaBuilder criteriaBuilder) {
                if (endsAt != null)
                    return criteriaBuilder.lessThanOrEqualTo(root.get("endsAt"), endsAt);
                return null;
            }
        };
    }
}