package com.microservices_example_app.booking.repository;

import com.microservices_example_app.booking.model.Town;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.JpaSpecificationExecutor;

import java.util.Optional;

public interface TownRepository extends JpaRepository<Town, Integer> {
    Optional<Town> findByNameIgnoreCase(String name);
    boolean existsByNameIgnoreCase(String name);
}