package main

import (
	"context"
	"fmt"
	"net/http"
	"os"
	"time"

	"github.com/gin-gonic/gin"
	"github.com/go-redis/redis/v8"
	amqp "github.com/rabbitmq/amqp091-go"
	"github.com/sirupsen/logrus"
)

var (
	redisClient *redis.Client
	rabbitConn  *amqp.Connection
	rabbitChan  *amqp.Channel
	rabbitQueue string
	logger      = logrus.New()
)

func getEnv(key string) string {
	value := os.Getenv(key)
	if value == "" {
		logger.Fatalf("Environment variable %s is not set", key)
	}
	return value
}

func connectToRedis(redisHost, redisPort string) error {
	redisClient = redis.NewClient(&redis.Options{
		Addr: fmt.Sprintf("%s:%s", redisHost, redisPort),
	})
	ctx := context.Background()
	_, err := redisClient.Ping(ctx).Result()
	return err
}

func connectToRabbitMQ(connStr string) error {
	var err error
	rabbitConn, err = amqp.Dial(connStr)
	if err != nil {
		return err
	}

	rabbitChan, err = rabbitConn.Channel()
	if err != nil {
		return err
	}

	_, err = rabbitChan.QueueDeclare(
		rabbitQueue,
		true,
		false,
		false,
		false,
		nil,
	)
	return err
}

func init() {
	redisHost := getEnv("REDIS_HOST")
	redisPort := getEnv("REDIS_PORT")
	rabbitHost := getEnv("RABBITMQ_HOST")
	rabbitPort := getEnv("RABBITMQ_PORT")
	rabbitUser := getEnv("RABBITMQ_USER")
	rabbitPass := getEnv("RABBITMQ_PASS")
	rabbitQueue = getEnv("RABBITMQ_QUEUE")

	connStr := fmt.Sprintf("amqp://%s:%s@%s:%s/", rabbitUser, rabbitPass, rabbitHost, rabbitPort)

	for i := 0; i < 5; i++ {
		err := connectToRedis(redisHost, redisPort)
		if err == nil {
			logger.Infof("Connected to Redis")
			break
		}
		logger.Errorf("Failed to connect to Redis: %v", err)
		if i == 4 {
			logger.Fatalf("Could not connect to Redis after 5 attempts")
		}
		time.Sleep(2 * time.Second)
	}

	for i := 0; i < 5; i++ {
		err := connectToRabbitMQ(connStr)
		if err == nil {
			logger.Infof("Connected to RabbitMQ")
			break
		}
		logger.Errorf("Failed to connect to RabbitMQ: %v", err)
		if i == 4 {
			logger.Fatalf("Could not connect to RabbitMQ after 5 attempts")
		}
		time.Sleep(2 * time.Second)
	}
}

func main() {
	r := gin.Default()
	apiPort := getEnv("QUEUE_API_PORT")

	r.GET("/check", func(c *gin.Context) {
		key := c.Query("key")
		if key == "" {
			c.JSON(http.StatusBadRequest, gin.H{"error": "Key is required"})
			return
		}

		ctx := context.Background()
		exists, err := redisClient.Exists(ctx, key).Result()
		if err != nil {
			logger.Errorf("Redis error: %v", err)
			c.JSON(http.StatusInternalServerError, gin.H{"error": "Redis error"})
			return
		}

		if exists > 0 {
			c.JSON(http.StatusConflict, gin.H{"message": "Key already exists"})
		} else {
			c.JSON(http.StatusOK, gin.H{"message": "Key does not exist"})
		}
	})

	r.POST("/submit", func(c *gin.Context) {
		var request struct {
			Key     string `json:"key" binding:"required"`
			Message string `json:"message" binding:"required"`
		}

		if err := c.ShouldBindJSON(&request); err != nil {
			c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
			return
		}

		ctx := context.Background()
		err := redisClient.Set(ctx, request.Key, request.Message, 0).Err()
		if err != nil {
			logger.Errorf("Redis error: %v", err)
			c.JSON(http.StatusInternalServerError, gin.H{"error": "Redis error"})
			return
		}

		err = rabbitChan.Publish(
			"",
			rabbitQueue,
			false,
			false,
			amqp.Publishing{
				ContentType: "text/plain",
				Body:        []byte(request.Message),
			},
		)
		if err != nil {
			logger.Errorf("RabbitMQ error: %v", err)
			c.JSON(http.StatusInternalServerError, gin.H{"error": "RabbitMQ error"})
			return
		}

		c.JSON(http.StatusOK, gin.H{"message": "Success"})
	})

	r.GET("/healthcheck", func(c *gin.Context) {
		ctx := context.Background()

		_, err := redisClient.Ping(ctx).Result()
		if err != nil {
			logger.Errorf("Redis health check failed: %v", err)
			c.JSON(http.StatusInternalServerError, gin.H{"status": "Redis connection failed"})
			return
		}

		if rabbitConn.IsClosed() {
			logger.Errorf("RabbitMQ health check failed: connection is closed")
			c.JSON(http.StatusInternalServerError, gin.H{"status": "RabbitMQ connection failed"})
			return
		}

		c.JSON(http.StatusOK, gin.H{"status": "All connections are healthy"})
	})

	logger.Infof("Starting server on port %s", apiPort)
	if err := r.Run(fmt.Sprintf(":%s", apiPort)); err != nil {
		logger.Fatalf("Failed to run server: %v", err)
	}
}
