package com.microservices_example_app.booking.specification;

import com.microservices_example_app.booking.model.Venue;
import jakarta.persistence.criteria.CriteriaBuilder;
import jakarta.persistence.criteria.CriteriaQuery;
import jakarta.persistence.criteria.Predicate;
import jakarta.persistence.criteria.Root;
import org.jspecify.annotations.Nullable;
import org.springframework.data.jpa.domain.Specification;

public class VenueSpecification {

    public static Specification<Venue> hasTownId(Integer townId) {
        return new Specification<Venue>() {
            @Override
            public @Nullable Predicate toPredicate(Root<Venue> root, CriteriaQuery<?> query, CriteriaBuilder criteriaBuilder) {
                if (townId != null)
                    return criteriaBuilder.equal(root.get("town").get("id"), townId);
                return null;
            }
        };
    }

    public static Specification<Venue> hasPlace(String place) {
        return new Specification<Venue>() {
            @Override
            public @Nullable Predicate toPredicate(Root<Venue> root, CriteriaQuery<?> query, CriteriaBuilder criteriaBuilder) {
                if (place != null && !place.isBlank())
                    return criteriaBuilder.like(criteriaBuilder.lower(root.get("place")), "%" + place.toLowerCase() + "%");
                return null;
            }
        };
    }

    public static Specification<Venue> hasCapacity(Integer capacity) {
        return new Specification<Venue>() {
            @Override
            public @Nullable Predicate toPredicate(Root<Venue> root, CriteriaQuery<?> query, CriteriaBuilder criteriaBuilder) {
                if (capacity != null)
                    return criteriaBuilder.equal(root.get("capacity"), capacity);
                return null;
            }
        };
    }

    public static Specification<Venue> hasCapacityGreaterThanOrEqual(Integer capacity) {
        return new Specification<Venue>() {
            @Override
            public @Nullable Predicate toPredicate(Root<Venue> root, CriteriaQuery<?> query, CriteriaBuilder criteriaBuilder) {
                if (capacity != null)
                    return criteriaBuilder.greaterThanOrEqualTo(root.get("capacity"), capacity);
                return null;
            }
        };
    }

    public static Specification<Venue> hasCapacityLessThanOrEqual(Integer capacity) {
        return new Specification<Venue>() {
            @Override
            public @Nullable Predicate toPredicate(Root<Venue> root, CriteriaQuery<?> query, CriteriaBuilder criteriaBuilder) {
                if (capacity != null)
                    return criteriaBuilder.lessThanOrEqualTo(root.get("capacity"), capacity);
                return null;
            }
        };
    }
}