package com.microservices_example_app.users;

import com.microservices_example_app.users.dto.*;
import com.microservices_example_app.users.event.ForgetPasswordEvent;
import com.microservices_example_app.users.event.SuccessfulRegistrationEmailEvent;
import com.microservices_example_app.users.exceptions.EmailForwardingException;
import com.microservices_example_app.users.exceptions.UserNotFoundException;
import com.microservices_example_app.users.model.Role;
import com.microservices_example_app.users.model.User;
import com.microservices_example_app.users.producers.NotificationKafkaAuthenticationProducer;
import com.microservices_example_app.users.repository.RoleRepository;
import com.microservices_example_app.users.repository.UserRepository;
import com.microservices_example_app.users.service.PasswordService;
import com.microservices_example_app.users.service.UserService;
import com.microservices_example_app.users.utils.JwtUtil;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.MockedStatic;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.data.domain.PageImpl;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.domain.Specification;
import org.springframework.test.util.ReflectionTestUtils;

import java.util.List;
import java.util.Optional;

import static org.assertj.core.api.Assertions.*;
import static org.mockito.ArgumentMatchers.*;
import static org.mockito.Mockito.*;

@ExtendWith(MockitoExtension.class)
class UserServiceTest {

    @Mock
    private UserRepository userDao;

    @Mock
    private RoleRepository roleRepository;

    @Mock
    private PasswordService passwordService;

    @Mock
    private NotificationKafkaAuthenticationProducer authenticationProducer;

    @InjectMocks
    private UserService userService;

    @BeforeEach
    void setUp() {
        ReflectionTestUtils.setField(userService, "resetPasswordUrl", "http://localhost:8080/reset-password");
        ReflectionTestUtils.setField(userService, "serviceName", "user-service");
    }

    @Test
    void register_shouldRegisterUserAndSendEmailEvent() {
        Role role = Role.builder()
                .id(1)
                .name("CUSTOMER")
                .build();

        User savedUser = User.builder()
                .id(10)
                .username("alex")
                .email("alex@test.com")
                .passwordHash("hashed")
                .userRole(role)
                .build();

        when(roleRepository.findByName("CUSTOMER")).thenReturn(Optional.of(role));
        when(passwordService.hash("123456")).thenReturn("hashed");
        when(userDao.save(any(User.class))).thenReturn(savedUser);

        UserRegistrationDto result = userService.register("alex@test.com", "123456", "CUSTOMER", "alex");

        assertThat(result).isNotNull();
        assertThat(result.getId()).isEqualTo(10);
        assertThat(result.getUsername()).isEqualTo("alex");
        assertThat(result.getEmail()).isEqualTo("alex@test.com");

        ArgumentCaptor<User> userCaptor = ArgumentCaptor.forClass(User.class);
        verify(userDao).save(userCaptor.capture());

        User actual = userCaptor.getValue();
        assertThat(actual.getUsername()).isEqualTo("alex");
        assertThat(actual.getEmail()).isEqualTo("alex@test.com");
        assertThat(actual.getPasswordHash()).isEqualTo("hashed");
        assertThat(actual.getUserRole().getName()).isEqualTo("CUSTOMER");

        verify(authenticationProducer).sendSuccessfulRegistrationEmail(any(SuccessfulRegistrationEmailEvent.class));
    }

    @Test
    void register_shouldThrowWhenRoleNotFound() {
        when(roleRepository.findByName("CUSTOMER")).thenReturn(Optional.empty());

        assertThatThrownBy(() -> userService.register("alex@test.com", "123456", "CUSTOMER", "alex"))
                .isInstanceOf(IllegalStateException.class)
                .hasMessage("Role not found");

        verify(passwordService, never()).hash(anyString());
        verify(userDao, never()).save(any());
        verify(authenticationProducer, never()).sendSuccessfulRegistrationEmail(any());
    }

    @Test
    void register_shouldNotFailWhenEmailProducerThrows() {
        Role role = Role.builder()
                .id(1)
                .name("CUSTOMER")
                .build();

        User savedUser = User.builder()
                .id(10)
                .username("alex")
                .email("alex@test.com")
                .passwordHash("hashed")
                .userRole(role)
                .build();

        when(roleRepository.findByName("CUSTOMER")).thenReturn(Optional.of(role));
        when(passwordService.hash("123456")).thenReturn("hashed");
        when(userDao.save(any(User.class))).thenReturn(savedUser);
        doThrow(new RuntimeException("Kafka down"))
                .when(authenticationProducer)
                .sendSuccessfulRegistrationEmail(any(SuccessfulRegistrationEmailEvent.class));

        UserRegistrationDto result = userService.register("alex@test.com", "123456", "CUSTOMER", "alex");

        assertThat(result.getId()).isEqualTo(10);
        assertThat(result.getEmail()).isEqualTo("alex@test.com");
        verify(userDao).save(any(User.class));
        verify(authenticationProducer).sendSuccessfulRegistrationEmail(any(SuccessfulRegistrationEmailEvent.class));
    }

    @Test
    void login_shouldReturnTokenAndUserId() {
        Role role = Role.builder()
                .id(1)
                .name("CUSTOMER")
                .build();

        User user = User.builder()
                .id(10)
                .username("alex")
                .email("alex@test.com")
                .passwordHash("hashed")
                .userRole(role)
                .build();

        when(userDao.findByEmail("alex@test.com")).thenReturn(Optional.of(user));
        when(passwordService.verify("123456", "hashed")).thenReturn(true);

        try (MockedStatic<JwtUtil> jwtUtilMock = mockStatic(JwtUtil.class)) {
            jwtUtilMock.when(() -> JwtUtil.generateToken(10, "alex", "alex@test.com", "CUSTOMER"))
                    .thenReturn("jwt-token");

            UserLoginResponseDto result = userService.login("alex@test.com", "123456");

            assertThat(result.getJwt()).isEqualTo("jwt-token");
            assertThat(result.getId()).isEqualTo(10);
        }
    }

    @Test
    void login_shouldThrowWhenUserNotFound() {
        when(userDao.findByEmail("alex@test.com")).thenReturn(Optional.empty());

        assertThatThrownBy(() -> userService.login("alex@test.com", "123456"))
                .isInstanceOf(UserNotFoundException.class)
                .hasMessage("Invalid email or password");

        verify(passwordService, never()).verify(anyString(), anyString());
    }

    @Test
    void login_shouldThrowWhenPasswordInvalid() {
        Role role = Role.builder()
                .id(1)
                .name("CUSTOMER")
                .build();

        User user = User.builder()
                .id(10)
                .username("alex")
                .email("alex@test.com")
                .passwordHash("hashed")
                .userRole(role)
                .build();

        when(userDao.findByEmail("alex@test.com")).thenReturn(Optional.of(user));
        when(passwordService.verify("123456", "hashed")).thenReturn(false);

        assertThatThrownBy(() -> userService.login("alex@test.com", "123456"))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessage("Invalid email or password");
    }

    @Test
    void getByEmail_shouldReturnUser() {
        Role role = Role.builder().id(1).name("CUSTOMER").build();
        User user = User.builder()
                .id(10)
                .username("alex")
                .email("alex@test.com")
                .passwordHash("hashed")
                .userRole(role)
                .build();

        when(userDao.findByEmail("alex@test.com")).thenReturn(Optional.of(user));

        UserResponseDto result = userService.getByEmail("alex@test.com");

        assertThat(result.getId()).isEqualTo(10);
        assertThat(result.getUsername()).isEqualTo("alex");
        assertThat(result.getEmail()).isEqualTo("alex@test.com");
        assertThat(result.getRole()).isEqualTo("CUSTOMER");
    }

    @Test
    void getByEmail_shouldThrowWhenUserNotFound() {
        when(userDao.findByEmail("alex@test.com")).thenReturn(Optional.empty());

        assertThatThrownBy(() -> userService.getByEmail("alex@test.com"))
                .isInstanceOf(UserNotFoundException.class)
                .hasMessage("User not found: alex@test.com");
    }

    @Test
    void restorePassword_shouldSendEmailWhenUserExists() {
        Role role = Role.builder().id(1).name("CUSTOMER").build();
        User user = User.builder()
                .id(10)
                .username("alex")
                .email("alex@test.com")
                .passwordHash("hashed")
                .userRole(role)
                .build();

        when(userDao.findByEmail("alex@test.com")).thenReturn(Optional.of(user));

        try (MockedStatic<JwtUtil> jwtUtilMock = mockStatic(JwtUtil.class)) {
            jwtUtilMock.when(() -> JwtUtil.generatePasswordResetToken(10, "alex@test.com"))
                    .thenReturn("reset-token");

            userService.restorePassword("alex@test.com");
        }

        verify(authenticationProducer).sendEmailToRestorePassword(any(ForgetPasswordEvent.class));
    }

    @Test
    void restorePassword_shouldDoNothingWhenUserNotFound() {
        when(userDao.findByEmail("unknown@test.com")).thenReturn(Optional.empty());

        userService.restorePassword("unknown@test.com");

        verify(authenticationProducer, never()).sendEmailToRestorePassword(any());
    }

    @Test
    void restorePassword_shouldThrowEmailForwardingExceptionWhenProducerFails() {
        Role role = Role.builder().id(1).name("CUSTOMER").build();
        User user = User.builder()
                .id(10)
                .username("alex")
                .email("alex@test.com")
                .passwordHash("hashed")
                .userRole(role)
                .build();

        when(userDao.findByEmail("alex@test.com")).thenReturn(Optional.of(user));
        doThrow(new RuntimeException("Kafka error"))
                .when(authenticationProducer)
                .sendEmailToRestorePassword(any(ForgetPasswordEvent.class));

        try (MockedStatic<JwtUtil> jwtUtilMock = mockStatic(JwtUtil.class)) {
            jwtUtilMock.when(() -> JwtUtil.generatePasswordResetToken(10, "alex@test.com"))
                    .thenReturn("reset-token");

            assertThatThrownBy(() -> userService.restorePassword("alex@test.com"))
                    .isInstanceOf(EmailForwardingException.class)
                    .hasMessageContaining("Error during email forming process:");
        }
    }

    @Test
    void getAll_shouldReturnAllUsers() {
        Role role = Role.builder().id(1).name("CUSTOMER").build();

        User user1 = User.builder().id(1).username("u1").email("u1@test.com").passwordHash("h1").userRole(role).build();
        User user2 = User.builder().id(2).username("u2").email("u2@test.com").passwordHash("h2").userRole(role).build();

        when(userDao.findAll()).thenReturn(List.of(user1, user2));

        List<UserResponseDto> result = userService.getAll();

        assertThat(result).hasSize(2);
        assertThat(result.getFirst().getEmail()).isEqualTo("u1@test.com");
    }

    @Test
    void getUsersByPage_shouldReturnPagedUsers() {
        Role role = Role.builder().id(1).name("CUSTOMER").build();
        User user = User.builder().id(1).username("u1").email("u1@test.com").passwordHash("h1").userRole(role).build();

        when(userDao.findAll(any(Pageable.class))).thenReturn(new PageImpl<>(List.of(user)));

        List<UserResponseDto> result = userService.getUsersByPage(1, 10);

        assertThat(result).hasSize(1);
        assertThat(result.getFirst().getId()).isEqualTo(1);
        verify(userDao).findAll(any(Pageable.class));
    }

    @Test
    void getById_shouldReturnUser() {
        Role role = Role.builder().id(1).name("CUSTOMER").build();
        User user = User.builder().id(10).username("alex").email("alex@test.com").passwordHash("h").userRole(role).build();

        when(userDao.findById(10)).thenReturn(Optional.of(user));

        UserResponseDto result = userService.getById(10);

        assertThat(result.getId()).isEqualTo(10);
        assertThat(result.getUsername()).isEqualTo("alex");
    }

    @Test
    void getById_shouldThrowWhenUserNotFound() {
        when(userDao.findById(10)).thenReturn(Optional.empty());

        assertThatThrownBy(() -> userService.getById(10))
                .isInstanceOf(UserNotFoundException.class)
                .hasMessage("no such user");
    }

    @Test
    void updateUser_shouldSaveWhenUserExists() {
        Role role = Role.builder().id(1).name("CUSTOMER").build();
        User existing = User.builder().id(10).username("alex").email("alex@test.com").passwordHash("h").userRole(role).build();
        User updated = User.builder().id(10).username("alex2").email("alex2@test.com").passwordHash("h2").userRole(role).build();

        when(userDao.findById(10)).thenReturn(Optional.of(existing));

        userService.updateUser(updated);

        verify(userDao).save(updated);
    }

    @Test
    void updateUser_shouldThrowWhenUserNotFound() {
        Role role = Role.builder().id(1).name("CUSTOMER").build();
        User updated = User.builder().id(10).username("alex2").email("alex2@test.com").passwordHash("h2").userRole(role).build();

        when(userDao.findById(10)).thenReturn(Optional.empty());

        assertThatThrownBy(() -> userService.updateUser(updated))
                .isInstanceOf(UserNotFoundException.class)
                .hasMessage("no user with such id");

        verify(userDao, never()).save(any());
    }

    @Test
    void deleteUser_shouldDeleteWhenUserExists() {
        UserDeleteRequestDto request = new UserDeleteRequestDto();
        request.setId(10);

        Role role = Role.builder().id(1).name("CUSTOMER").build();
        User existing = User.builder().id(10).username("alex").email("alex@test.com").passwordHash("h").userRole(role).build();

        when(userDao.findById(10)).thenReturn(Optional.of(existing));

        userService.deleteUser(request);

        verify(userDao).deleteById(10);
    }

    @Test
    void deleteUser_shouldThrowWhenUserNotFound() {
        UserDeleteRequestDto request = new UserDeleteRequestDto();
        request.setId(10);

        when(userDao.findById(10)).thenReturn(Optional.empty());

        assertThatThrownBy(() -> userService.deleteUser(request))
                .isInstanceOf(UserNotFoundException.class)
                .hasMessage("no user with such id");

        verify(userDao, never()).deleteById(anyInt());
    }

    @Test
    void deleteByFilter_shouldDeleteUsersAndReturnCount() {
        UserDeleteRequestDto request = new UserDeleteRequestDto();
        request.setEmail("alex@test.com");
        request.setUsername("alex");
        request.setRole("CUSTOMER");

        Role role = Role.builder().id(1).name("CUSTOMER").build();
        User user1 = User.builder().id(1).username("alex").email("alex@test.com").passwordHash("h").userRole(role).build();
        User user2 = User.builder().id(2).username("alex").email("alex@test.com").passwordHash("h").userRole(role).build();

        when(roleRepository.findByName("CUSTOMER")).thenReturn(Optional.of(role));
        when(userDao.findAll(any(Specification.class))).thenReturn(List.of(user1, user2));

        long result = userService.deleteByFilter(request);

        assertThat(result).isEqualTo(2);
        verify(userDao).deleteAll(List.of(user1, user2));
    }

    @Test
    void deleteByFilter_shouldThrowWhenRoleNotFound() {
        UserDeleteRequestDto request = new UserDeleteRequestDto();
        request.setRole("CUSTOMER");

        when(roleRepository.findByName("CUSTOMER")).thenReturn(Optional.empty());

        assertThatThrownBy(() -> userService.deleteByFilter(request))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessage("Role not found: CUSTOMER");
    }

    @Test
    void searchByFilter_shouldReturnUsers() {
        UserSerchRequestDto filter = new UserSerchRequestDto();
        filter.setEmail("alex@test.com");
        filter.setUsername("alex");
        filter.setRole("CUSTOMER");

        Role role = Role.builder().id(1).name("CUSTOMER").build();
        User user = User.builder().id(10).username("alex").email("alex@test.com").passwordHash("h").userRole(role).build();

        when(roleRepository.findByName("CUSTOMER")).thenReturn(Optional.of(role));
        when(userDao.findAll(any(Specification.class))).thenReturn(List.of(user));

        List<UserResponseDto> result = userService.searchByFilter(filter);

        assertThat(result).hasSize(1);
        assertThat(result.getFirst().getEmail()).isEqualTo("alex@test.com");
    }

    @Test
    void searchByFilter_shouldThrowWhenRoleNotFound() {
        UserSerchRequestDto filter = new UserSerchRequestDto();
        filter.setRole("CUSTOMER");

        when(roleRepository.findByName("CUSTOMER")).thenReturn(Optional.empty());

        assertThatThrownBy(() -> userService.searchByFilter(filter))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessage("Role not found: CUSTOMER");
    }

    @Test
    void searchByFilterPaged_shouldReturnUsers() {
        UserSerchRequestDto filter = new UserSerchRequestDto();
        filter.setEmail("alex@test.com");
        filter.setUsername("alex");
        filter.setRole("CUSTOMER");

        Role role = Role.builder().id(1).name("CUSTOMER").build();
        User user = User.builder().id(10).username("alex").email("alex@test.com").passwordHash("h").userRole(role).build();

        when(roleRepository.findByName("CUSTOMER")).thenReturn(Optional.of(role));
        when(userDao.findAll(any(Specification.class), any(Pageable.class)))
                .thenReturn(new PageImpl<>(List.of(user)));

        List<UserResponseDto> result = userService.searchByFilter(filter, 1, 10);

        assertThat(result).hasSize(1);
        assertThat(result.getFirst().getId()).isEqualTo(10);
    }

    @Test
    void searchByFilterPaged_shouldThrowWhenPageInvalid() {
        UserSerchRequestDto filter = new UserSerchRequestDto();

        assertThatThrownBy(() -> userService.searchByFilter(filter, 0, 10))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessage("Page must be >= 1");
    }

    @Test
    void searchByFilterPaged_shouldThrowWhenSizeInvalid() {
        UserSerchRequestDto filter = new UserSerchRequestDto();

        assertThatThrownBy(() -> userService.searchByFilter(filter, 1, 0))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessage("Size must be >= 1");
    }

    @Test
    void updateUserById_shouldUpdateUser() {
        UserUpdateRequestDto request = new UserUpdateRequestDto();
        request.setId(10);
        request.setEmail("new@test.com");
        request.setUsername("newname");
        request.setRole("ADMIN");
        request.setPassword("newpass");

        Role oldRole = Role.builder().id(1).name("CUSTOMER").build();
        Role newRole = Role.builder().id(2).name("ADMIN").build();

        User existing = User.builder()
                .id(10)
                .username("alex")
                .email("old@test.com")
                .passwordHash("oldHash")
                .userRole(oldRole)
                .build();

        User saved = User.builder()
                .id(10)
                .username("newname")
                .email("new@test.com")
                .passwordHash("newHash")
                .userRole(newRole)
                .build();

        when(userDao.findById(10)).thenReturn(Optional.of(existing));
        when(userDao.findByEmail("new@test.com")).thenReturn(Optional.empty());
        when(roleRepository.findByName("ADMIN")).thenReturn(Optional.of(newRole));
        when(passwordService.hash("newpass")).thenReturn("newHash");
        when(userDao.save(any(User.class))).thenReturn(saved);

        UserResponseDto result = userService.updateUserById(request);

        assertThat(result.getId()).isEqualTo(10);
        assertThat(result.getUsername()).isEqualTo("newname");
        assertThat(result.getEmail()).isEqualTo("new@test.com");
        assertThat(result.getRole()).isEqualTo("ADMIN");

        ArgumentCaptor<User> captor = ArgumentCaptor.forClass(User.class);
        verify(userDao).save(captor.capture());

        User actual = captor.getValue();
        assertThat(actual.getId()).isEqualTo(10);
        assertThat(actual.getUsername()).isEqualTo("newname");
        assertThat(actual.getEmail()).isEqualTo("new@test.com");
        assertThat(actual.getPasswordHash()).isEqualTo("newHash");
        assertThat(actual.getUserRole().getName()).isEqualTo("ADMIN");
    }

    @Test
    void updateUserById_shouldThrowWhenUserNotFound() {
        UserUpdateRequestDto request = new UserUpdateRequestDto();
        request.setId(10);

        when(userDao.findById(10)).thenReturn(Optional.empty());

        assertThatThrownBy(() -> userService.updateUserById(request))
                .isInstanceOf(UserNotFoundException.class)
                .hasMessage("No user with id=10");

        verify(userDao, never()).save(any());
    }

    @Test
    void updateUserById_shouldThrowWhenEmailAlreadyInUse() {
        UserUpdateRequestDto request = new UserUpdateRequestDto();
        request.setId(10);
        request.setEmail("taken@test.com");

        Role role = Role.builder().id(1).name("CUSTOMER").build();

        User existing = User.builder()
                .id(10)
                .username("alex")
                .email("old@test.com")
                .passwordHash("oldHash")
                .userRole(role)
                .build();

        User anotherUser = User.builder()
                .id(20)
                .username("other")
                .email("taken@test.com")
                .passwordHash("hash")
                .userRole(role)
                .build();

        when(userDao.findById(10)).thenReturn(Optional.of(existing));
        when(userDao.findByEmail("taken@test.com")).thenReturn(Optional.of(anotherUser));

        assertThatThrownBy(() -> userService.updateUserById(request))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessage("Email already in use: taken@test.com");

        verify(userDao, never()).save(any());
    }

    @Test
    void updateUserById_shouldThrowWhenRoleNotFound() {
        UserUpdateRequestDto request = new UserUpdateRequestDto();
        request.setId(10);
        request.setRole("ADMIN");

        Role role = Role.builder().id(1).name("CUSTOMER").build();
        User existing = User.builder()
                .id(10)
                .username("alex")
                .email("old@test.com")
                .passwordHash("oldHash")
                .userRole(role)
                .build();

        when(userDao.findById(10)).thenReturn(Optional.of(existing));
        when(roleRepository.findByName("ADMIN")).thenReturn(Optional.empty());

        assertThatThrownBy(() -> userService.updateUserById(request))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessage("Role not found: ADMIN");

        verify(userDao, never()).save(any());
    }
}