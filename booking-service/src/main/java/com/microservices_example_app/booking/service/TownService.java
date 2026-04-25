package com.microservices_example_app.booking.service;

import com.microservices_example_app.booking.dto.TownCreateRequestDto;
import com.microservices_example_app.booking.dto.TownResponseDto;
import com.microservices_example_app.booking.exceptions.NotFoundException;
import com.microservices_example_app.booking.model.Town;
import com.microservices_example_app.booking.repository.TownRepository;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;

import java.util.List;

@Service
@RequiredArgsConstructor
@Slf4j
public class TownService {

    private final TownRepository townRepository;

    public TownResponseDto create(TownCreateRequestDto requestDto) {
        log.info("Creating town: {}", requestDto.getName());
        Town town = Town.builder()
                .name(requestDto.getName())
                .build();

        return toResponseDto(townRepository.save(town));
    }

    public TownResponseDto getById(Integer id) {
        log.info("Fetching town with id: {}", id);
        Town town = townRepository.findById(id)
                .orElseThrow(() -> new NotFoundException("Town not found"));
        return toResponseDto(town);
    }

    public List<TownResponseDto> getAll() {
        return townRepository.findAll()
                .stream()
                .map(this::toResponseDto)
                .toList();
    }

    public void delete(Integer id) {
        townRepository.deleteById(id);
    }

    private TownResponseDto toResponseDto(Town town) {
        return TownResponseDto.builder()
                .id(town.getId())
                .name(town.getName())
                .build();
    }
}