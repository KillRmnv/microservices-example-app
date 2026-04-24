package com.microservices_example_app.users.dto;

import com.microservices_example_app.users.model.Role;
import com.microservices_example_app.users.model.User;
import jakarta.persistence.criteria.CriteriaBuilder;
import jakarta.persistence.criteria.CriteriaQuery;
import jakarta.persistence.criteria.Predicate;
import jakarta.persistence.criteria.Root;
import org.jspecify.annotations.Nullable;
import org.springframework.data.jpa.domain.Specification;

public class UserSpecification {
    public static Specification<User> hasUsername(String username) {
        return new Specification<User>() {
            @Override
            public @Nullable Predicate toPredicate(Root<User> root, CriteriaQuery<?> query, CriteriaBuilder criteriaBuilder) {
                if (username != null && !username.isBlank())
                    return criteriaBuilder.equal(root.get("username"), username);
                else
                    return null;
            }
        };
    }

    public static Specification<User> hasEmail(String email){
        return new Specification<User>() {
            @Override
            public @Nullable Predicate toPredicate(Root<User> root, CriteriaQuery<?> query, CriteriaBuilder criteriaBuilder) {
                if(email!=null&&!email.isBlank())
                    return criteriaBuilder.equal(root.get("email"),email);
                return null;
            }
        };
    }

    public static Specification<User> hasPassword(String passwordHash){
        return new Specification<User>() {
            @Override
            public @Nullable Predicate toPredicate(Root<User> root, CriteriaQuery<?> query, CriteriaBuilder criteriaBuilder) {
                if(passwordHash!=null&&!passwordHash.isBlank())
                    return criteriaBuilder.equal(root.get("passwordHash"),passwordHash);
                return null;
            }
        };
    }

    public static Specification<User> hasRole(Role role){
        return new Specification<User>() {
            @Override
            public @Nullable Predicate toPredicate(Root<User> root, CriteriaQuery<?> query, CriteriaBuilder criteriaBuilder) {
                if(role!=null)
                    return criteriaBuilder.equal(root.get("role"),role);
                return null;
            }
        };
    }
}
