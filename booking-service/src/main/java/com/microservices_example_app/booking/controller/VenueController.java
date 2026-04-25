package com.microservices_example_app.booking.controller;

import com.microservices_example_app.booking.dto.*;
import com.microservices_example_app.booking.service.VenueService;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.*;

import java.util.List;

@RestController
@RequestMapping("/booking/venues")
@RequiredArgsConstructor
public class VenueController {

    private final VenueService venueService;

    @PostMapping
    public VenueResponseDto create(@RequestBody VenueCreateRequestDto requestDto) {
        return venueService.create(requestDto);
    }

    @GetMapping("/{id}")
    public VenueResponseDto getById(@PathVariable Integer id) {
        return venueService.getById(id);
    }

    @GetMapping("/search")
    public List<VenueResponseDto> searchByFilter(@ModelAttribute VenueSearchRequestDto filter,
                                                 @RequestParam(defaultValue = "1") int page,
                                                 @RequestParam(defaultValue = "10") int size) {
        return venueService.searchByFilter(filter, page, size);
    }

    @PutMapping("/{id}")
    public VenueResponseDto updateById(@PathVariable Integer id,
                                       @RequestBody VenueUpdateRequestDto requestDto) {
        requestDto.setId(id);
        return venueService.updateVenueById(requestDto);
    }

    @DeleteMapping("/{id}")
    public void deleteById(@PathVariable Integer id) {
        venueService.deleteById(id);
    }

    @DeleteMapping("/search")
    public long deleteByFilter(@RequestBody VenueDeleteRequestDto requestDto) {
        return venueService.deleteByFilter(requestDto);
    }
}