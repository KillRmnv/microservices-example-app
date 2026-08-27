package com.microservices_example_app.users;

import com.microservices_example_app.users.dto.UserSpecification;
import com.microservices_example_app.users.model.Role;
import com.microservices_example_app.users.model.User;
import jakarta.persistence.criteria.CriteriaBuilder;
import jakarta.persistence.criteria.CriteriaQuery;
import jakarta.persistence.criteria.Predicate;
import jakarta.persistence.criteria.Root;
import org.junit.jupiter.api.Test;
import org.springframework.data.jpa.domain.Specification;

import static org.assertj.core.api.Assertions.*;
import static org.mockito.Mockito.*;

class UserSpecificationTest {

    @SuppressWarnings("unchecked")
    private final Root<User> root = mock(Root.class);
    @SuppressWarnings("unchecked")
    private final CriteriaQuery<?> query = mock(CriteriaQuery.class);
    private final CriteriaBuilder cb = mock(CriteriaBuilder.class);

    // ==================== hasUsername ====================

    @Test
    void hasUsername_shouldReturnPredicateWhenValid() {
        Specification<User> spec = UserSpecification.hasUsername("alex");
        Predicate dummy = mock(Predicate.class);
        when(cb.equal(root.get("username"), "alex")).thenReturn(dummy);

        Predicate result = spec.toPredicate(root, query, cb);

        assertThat(result).isNotNull();
    }

    @Test
    void hasUsername_shouldReturnNullWhenNull() {
        Specification<User> spec = UserSpecification.hasUsername(null);

        Predicate result = spec.toPredicate(root, query, cb);

        assertThat(result).isNull();
    }

    @Test
    void hasUsername_shouldReturnNullWhenBlank() {
        Specification<User> spec = UserSpecification.hasUsername("  ");

        Predicate result = spec.toPredicate(root, query, cb);

        assertThat(result).isNull();
    }

    // ==================== hasEmail ====================

    @Test
    void hasEmail_shouldReturnPredicateWhenValid() {
        Specification<User> spec = UserSpecification.hasEmail("a@b.com");
        Predicate dummy = mock(Predicate.class);
        when(cb.equal(root.get("email"), "a@b.com")).thenReturn(dummy);

        Predicate result = spec.toPredicate(root, query, cb);

        assertThat(result).isNotNull();
    }

    @Test
    void hasEmail_shouldReturnNullWhenNull() {
        Specification<User> spec = UserSpecification.hasEmail(null);

        Predicate result = spec.toPredicate(root, query, cb);

        assertThat(result).isNull();
    }

    @Test
    void hasEmail_shouldReturnNullWhenBlank() {
        Specification<User> spec = UserSpecification.hasEmail("");

        Predicate result = spec.toPredicate(root, query, cb);

        assertThat(result).isNull();
    }

    // ==================== hasPassword ====================

    @Test
    void hasPassword_shouldReturnPredicateWhenValid() {
        Specification<User> spec = UserSpecification.hasPassword("hash123");
        Predicate dummy = mock(Predicate.class);
        when(cb.equal(root.get("passwordHash"), "hash123")).thenReturn(dummy);

        Predicate result = spec.toPredicate(root, query, cb);

        assertThat(result).isNotNull();
    }

    @Test
    void hasPassword_shouldReturnNullWhenNull() {
        Specification<User> spec = UserSpecification.hasPassword(null);

        Predicate result = spec.toPredicate(root, query, cb);

        assertThat(result).isNull();
    }

    @Test
    void hasPassword_shouldReturnNullWhenBlank() {
        Specification<User> spec = UserSpecification.hasPassword("   ");

        Predicate result = spec.toPredicate(root, query, cb);

        assertThat(result).isNull();
    }

    // ==================== hasRole ====================

    @Test
    void hasRole_shouldReturnPredicateWhenValid() {
        Role role = Role.builder().id(1).name("CUSTOMER").build();
        Specification<User> spec = UserSpecification.hasRole(role);
        Predicate dummy = mock(Predicate.class);
        when(cb.equal(root.get("userRole"), role)).thenReturn(dummy);

        Predicate result = spec.toPredicate(root, query, cb);

        assertThat(result).isNotNull();
    }

    @Test
    void hasRole_shouldReturnNullWhenNull() {
        Specification<User> spec = UserSpecification.hasRole(null);

        Predicate result = spec.toPredicate(root, query, cb);

        assertThat(result).isNull();
    }
}
