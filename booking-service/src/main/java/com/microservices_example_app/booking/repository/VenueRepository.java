package com.microservices_example_app.booking.repository;

import com.microservices_example_app.booking.model.Venue;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.JpaSpecificationExecutor;
import org.springframework.stereotype.Repository;

import java.util.List;
@Repository
public interface VenueRepository extends JpaRepository<Venue, Integer>, JpaSpecificationExecutor<Venue> {
    List<Venue> findByTownId(Integer townId);
    List<Venue> findByPlaceContainingIgnoreCase(String place);
}