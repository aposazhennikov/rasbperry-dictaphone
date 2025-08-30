package logger

import (
	"fmt"
	"log"
	"os"
	"strings"
	"time"

	"github.com/getsentry/sentry-go"
)

// Logger represents application logger.
type Logger struct {
	level       Level
	sentryHub   *sentry.Hub
	debugLogger *log.Logger
	infoLogger  *log.Logger
	warnLogger  *log.Logger
	errorLogger *log.Logger
}

// Level represents log level.
type Level int

const (
	// DebugLevel logs debug messages.
	DebugLevel Level = iota
	// InfoLevel logs info messages.
	InfoLevel
	// WarnLevel logs warning messages.
	WarnLevel
	// ErrorLevel logs error messages.
	ErrorLevel
)

// New creates a new logger instance.
func New(level string, sentryDSN string, sentryEnabled bool) (*Logger, error) {
	l := &Logger{}

	// Parse log level.
	switch strings.ToLower(level) {
	case "debug":
		l.level = DebugLevel
	case "info":
		l.level = InfoLevel
	case "warn", "warning":
		l.level = WarnLevel
	case "error":
		l.level = ErrorLevel
	default:
		l.level = InfoLevel
	}

	// Initialize standard loggers.
	l.debugLogger = log.New(os.Stdout, "[DEBUG] ", log.LstdFlags|log.Lshortfile)
	l.infoLogger = log.New(os.Stdout, "[INFO] ", log.LstdFlags)
	l.warnLogger = log.New(os.Stderr, "[WARN] ", log.LstdFlags)
	l.errorLogger = log.New(os.Stderr, "[ERROR] ", log.LstdFlags|log.Lshortfile)

	// Initialize Sentry if enabled.
	if sentryEnabled && sentryDSN != "" {
		err := sentry.Init(sentry.ClientOptions{
			Dsn:              sentryDSN,
			Debug:            l.level == DebugLevel,
			AttachStacktrace: true,
			TracesSampleRate: 1.0,
		})
		if err != nil {
			return nil, fmt.Errorf("failed to initialize Sentry: %w", err)
		}

		l.sentryHub = sentry.CurrentHub()
		l.Info("Sentry initialized successfully")
	}

	return l, nil
}

// Debug logs debug message.
func (l *Logger) Debug(msg string, args ...interface{}) {
	if l.level > DebugLevel {
		return
	}

	message := fmt.Sprintf(msg, args...)
	l.debugLogger.Print(message)
}

// Info logs info message.
func (l *Logger) Info(msg string, args ...interface{}) {
	if l.level > InfoLevel {
		return
	}

	message := fmt.Sprintf(msg, args...)
	l.infoLogger.Print(message)
}

// Warn logs warning message.
func (l *Logger) Warn(msg string, args ...interface{}) {
	if l.level > WarnLevel {
		return
	}

	message := fmt.Sprintf(msg, args...)
	l.warnLogger.Print(message)

	if l.sentryHub != nil {
		l.sentryHub.CaptureMessage(message)
	}
}

// Error logs error message.
func (l *Logger) Error(msg string, args ...interface{}) {
	if l.level > ErrorLevel {
		return
	}

	message := fmt.Sprintf(msg, args...)
	l.errorLogger.Print(message)

	if l.sentryHub != nil {
		l.sentryHub.CaptureMessage(message)
	}
}

// ErrorWithException logs error with exception.
func (l *Logger) ErrorWithException(err error, msg string, args ...interface{}) {
	message := fmt.Sprintf(msg, args...)
	fullMessage := fmt.Sprintf("%s: %v", message, err)
	l.errorLogger.Print(fullMessage)

	if l.sentryHub != nil {
		l.sentryHub.CaptureException(err)
	}
}

// Fatal logs fatal error and exits.
func (l *Logger) Fatal(msg string, args ...interface{}) {
	message := fmt.Sprintf(msg, args...)
	l.errorLogger.Print(message)

	if l.sentryHub != nil {
		l.sentryHub.CaptureMessage(message)
		l.sentryHub.Flush(2 * time.Second)
	}

	os.Exit(1)
}

// FatalWithException logs fatal error with exception and exits.
func (l *Logger) FatalWithException(err error, msg string, args ...interface{}) {
	message := fmt.Sprintf(msg, args...)
	fullMessage := fmt.Sprintf("%s: %v", message, err)
	l.errorLogger.Print(fullMessage)

	if l.sentryHub != nil {
		l.sentryHub.CaptureException(err)
		l.sentryHub.Flush(2 * time.Second)
	}

	os.Exit(1)
}

// AddBreadcrumb adds breadcrumb to Sentry.
func (l *Logger) AddBreadcrumb(category, message string, level sentry.Level) {
	if l.sentryHub != nil {
		l.sentryHub.AddBreadcrumb(&sentry.Breadcrumb{
			Category: category,
			Message:  message,
			Level:    level,
		}, nil)
	}
}

// SetContext sets context for Sentry.
func (l *Logger) SetContext(key string, context map[string]interface{}) {
	if l.sentryHub != nil {
		l.sentryHub.ConfigureScope(func(scope *sentry.Scope) {
			scope.SetContext(key, context)
		})
	}
}

// Close flushes and closes the logger.
func (l *Logger) Close() {
	if l.sentryHub != nil {
		l.sentryHub.Flush(2 * time.Second)
	}
}
