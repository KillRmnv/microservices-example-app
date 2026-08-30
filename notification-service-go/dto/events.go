package dto

type SuccessfulRegistrationEmailEvent struct {
	Email         string `json:"email"`
	SourceService string `json:"sourceService"`
	Username      string `json:"username"`
}

type SuccessfulBookingEvent struct {
	Email         string `json:"email"`
	Username      string `json:"username"`
	Event         string `json:"event"`
	SourceService string `json:"sourceService"`
}

type TicketRefundEvent struct {
	Email         string `json:"email"`
	Username      string `json:"username"`
	EventTitle    string `json:"eventTitle"`
	SourceService string `json:"sourceService"`
}

type ForgetPasswordEvent struct {
	Email         string `json:"email"`
	SourceService string `json:"sourceService"`
	ResetURL      string `json:"resetUrl"`
}

type UserUpdatedEvent struct {
	UserID        int    `json:"userId"`
	Email         string `json:"email"`
	Username      string `json:"username"`
	Role          string `json:"role"`
	SourceService string `json:"sourceService"`
}

type UserDeletedEvent struct {
	UserID        int    `json:"userId"`
	Email         string `json:"email"`
	Username      string `json:"username"`
	SourceService string `json:"sourceService"`
}

type UserNotificationDto struct {
	Email    string `json:"email"`
	Username string `json:"username"`
}

type MassDeleteEventMailingEvent struct {
	Users         []UserNotificationDto `json:"users"`
	SourceService string                 `json:"sourceService"`
	Events        []string               `json:"events"`
}

type MassUpdateEventMailingEvent struct {
	Users              []UserNotificationDto `json:"users"`
	SourceService      string                 `json:"sourceService"`
	Events             []string               `json:"events"`
	ChangesDescription string                 `json:"changesDescription"`
}
