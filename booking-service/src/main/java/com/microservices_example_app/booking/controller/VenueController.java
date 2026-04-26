package com.microservices_example_app.booking.controller;

import com.microservices_example_app.booking.dto.*;
import com.microservices_example_app.booking.service.VenueService;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.web.bind.annotation.*;

import java.util.List;

@RestController
@RequestMapping("/booking/venues")
@RequiredArgsConstructor
@Slf4j
public class VenueController {

    private final VenueService venueService;

    @PostMapping
    public VenueResponseDto create(@Valid @RequestBody VenueCreateRequestDto requestDto) {
        log.info("Creating new venue in town id: {}", requestDto.getTownId());
        return venueService.create(requestDto);
    }

    @GetMapping("/{id}")
    public VenueResponseDto getById(@PathVariable Integer id) {
        log.info("Fetching venue with id: {}", id);
        return venueService.getById(id);
    }

    @GetMapping("/search")
    public List<VenueResponseDto> searchByFilter(@Valid @ModelAttribute VenueSearchRequestDto filter,
                                                 @RequestParam(defaultValue = "1") int page,
                                                 @RequestParam(defaultValue = "10") int size) {
        return venueService.searchByFilter(filter, page, size);
    }

    @PutMapping("/{id}")
    public VenueResponseDto updateById(@PathVariable Integer id,
                                       @Valid @RequestBody VenueUpdateRequestDto requestDto) {
        requestDto.setId(id);
        return venueService.updateVenueById(requestDto);
    }

    @DeleteMapping("/{id}")
    public void deleteById(@PathVariable Integer id) {
        log.info("Deleting venue with id: {}", id);
        venueService.deleteById(id);
    }

    @DeleteMapping("/search")
    public long deleteByFilter(@Valid @RequestBody VenueDeleteRequestDto requestDto) {
        return venueService.deleteByFilter(requestDto);
    }
}