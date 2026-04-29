package com.microservices_example_app.booking.controller;

import com.microservices_example_app.booking.dto.TownCreateRequestDto;
import com.microservices_example_app.booking.dto.TownResponseDto;
import com.microservices_example_app.booking.dto.TownUpdateRequestDto;
import com.microservices_example_app.booking.service.TownService;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.web.bind.annotation.*;

import java.util.List;

@RestController
@RequestMapping("/booking/towns")
@RequiredArgsConstructor
@Slf4j
public class TownController {

    private final TownService townService;

    @PostMapping
    public TownResponseDto create(@Valid @RequestBody TownCreateRequestDto requestDto) {
        log.info("Creating new town: {}", requestDto.getName());
        return townService.create(requestDto);
    }

    @GetMapping("/{id}")
    public TownResponseDto getById(@PathVariable Integer id) {
        log.info("Fetching town with id: {}", id);
        return townService.getById(id);
    }

    @GetMapping
    public List<TownResponseDto> getAll() {
        log.info("Fetching all towns");
        return townService.getAll();
    }

    @PutMapping("/{id}")
    public TownResponseDto updateById(@PathVariable Integer id,
                                      @Valid @RequestBody TownUpdateRequestDto requestDto) {
        log.info("Updating town with id: {}", id);
        requestDto.setId(id);
        return townService.updateTownById(requestDto);
    }

    @DeleteMapping("/{id}")
    public void deleteById(@PathVariable Integer id) {
        log.info("Deleting town with id: {}", id);
        townService.delete(id);
    }
}