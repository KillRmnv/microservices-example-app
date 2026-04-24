package com.microservices_example_app.booking.specification;

import com.microservices_example_app.booking.model.Seat;
import jakarta.persistence.criteria.CriteriaBuilder;
import jakarta.persistence.criteria.CriteriaQuery;
import jakarta.persistence.criteria.Predicate;
import jakarta.persistence.criteria.Root;
import org.jspecify.annotations.Nullable;
import org.springframework.data.jpa.domain.Specification;

public class SeatSpecification {

    public static Specification<Seat> hasVenueId(Integer venueId) {
        return new Specification<Seat>() {
            @Override
            public @Nullable Predicate toPredicate(Root<Seat> root, CriteriaQuery<?> query, CriteriaBuilder criteriaBuilder) {
                if (venueId != null)
                    return criteriaBuilder.equal(root.get("venue").get("id"), venueId);
                return null;
            }
        };
    }

    public static Specification<Seat> hasSector(String sector) {
        return new Specification<Seat>() {
            @Override
            public @Nullable Predicate toPredicate(Root<Seat> root, CriteriaQuery<?> query, CriteriaBuilder criteriaBuilder) {
                if (sector != null && !sector.isBlank())
                    return criteriaBuilder.equal(criteriaBuilder.lower(root.get("sector")), sector.toLowerCase());
                return null;
            }
        };
    }

    public static Specification<Seat> hasRow(String row) {
        return new Specification<Seat>() {
            @Override
            public @Nullable Predicate toPredicate(Root<Seat> root, CriteriaQuery<?> query, CriteriaBuilder criteriaBuilder) {
                if (row != null && !row.isBlank())
                    return criteriaBuilder.equal(criteriaBuilder.lower(root.get("row")), row.toLowerCase());
                return null;
            }
        };
    }

    public static Specification<Seat> hasNumber(String number) {
        return new Specification<Seat>() {
            @Override
            public @Nullable Predicate toPredicate(Root<Seat> root, CriteriaQuery<?> query, CriteriaBuilder criteriaBuilder) {
                if (number != null && !number.isBlank())
                    return criteriaBuilder.equal(criteriaBuilder.lower(root.get("number")), number.toLowerCase());
                return null;
            }
        };
    }
}