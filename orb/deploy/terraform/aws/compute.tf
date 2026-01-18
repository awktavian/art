resource "aws_lb" "app" {
  name               = "${var.app_name}-${var.environment_name}-alb"
  load_balancer_type = "application"
  subnets            = [for s in aws_subnet.public : s.id]
  security_groups    = [aws_security_group.alb.id]
}

resource "aws_lb_target_group" "app" {
  name        = "${var.app_name}-${var.environment_name}-tg"
  port        = 8001
  protocol    = "HTTP"
  vpc_id      = aws_vpc.this.id
  target_type = "ip"

  health_check {
    path                = "/health"
    matcher             = "200"
    healthy_threshold   = 2
    unhealthy_threshold = 2
    timeout             = 5
    interval            = 15
  }
}

resource "aws_lb_listener" "http" {
  load_balancer_arn = aws_lb.app.arn
  port              = 80
  protocol          = "HTTP"

  # Redirect HTTP to HTTPS in production
  default_action {
    type = "redirect"
    redirect {
      port        = "443"
      protocol    = "HTTPS"
      status_code = "HTTP_301"
    }
  }
}

resource "aws_lb_listener" "https" {
  load_balancer_arn = aws_lb.app.arn
  port              = 443
  protocol          = "HTTPS"
  ssl_policy        = "ELBSecurityPolicy-TLS13-1-2-2021-06"
  certificate_arn   = var.acm_certificate_arn

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.app.arn
  }
}

resource "aws_ecs_cluster" "this" {
  name = "${var.app_name}-${var.environment_name}"
}

resource "aws_iam_role" "task_exec" {
  name               = "${var.app_name}-${var.environment_name}-task-exec"
  assume_role_policy = data.aws_iam_policy_document.ecs_tasks_assume.json
}

data "aws_iam_policy_document" "ecs_tasks_assume" {
  statement {
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["ecs-tasks.amazonaws.com"]
    }
  }
}

resource "aws_iam_role_policy_attachment" "task_exec_attach" {
  role       = aws_iam_role.task_exec.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

resource "aws_ecs_task_definition" "app" {
  family                   = "${var.app_name}-${var.environment_name}"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = "1024"
  memory                   = "2048"
  execution_role_arn       = aws_iam_role.task_exec.arn

  container_definitions = jsonencode([
    {
      name      = "api"
      image     = var.container_image
      essential = true
      portMappings = [
        {
          containerPort = 8001
          hostPort      = 8001
          protocol      = "tcp"
        },
        {
          containerPort = 9090
          hostPort      = 9090
          protocol      = "tcp"
        }
      ]
      environment = [
        # Application
        { name = "ENVIRONMENT", value = var.environment_name },
        { name = "KAGAMI_PUBLIC_URL", value = var.public_url },
        { name = "PORT", value = "8001" },
        { name = "KAGAMI_BOOT_MODE", value = "full" },

        # =================================================================
        # UNIFIED CLUSTER CONFIGURATION
        # All clustering via kagami.core.cluster.UnifiedClusterManager
        # =================================================================
        { name = "KAGAMI_CLUSTER_NAME", value = "${var.app_name}-${var.environment_name}" },

        # Redis (ElastiCache)
        { name = "REDIS_URL", value = "redis://${aws_elasticache_cluster.redis.cache_nodes[0].address}:6379/0" },
        { name = "REDIS_MAX_CONNECTIONS", value = "200" },

        # Database (RDS/CockroachDB)
        { name = "DATABASE_URL", value = "postgresql://${var.db_username}:${var.db_password}@${aws_db_instance.postgres[0].endpoint}/${var.db_name}" },
        { name = "DB_POOL_SIZE", value = "100" },
        { name = "DB_MAX_OVERFLOW", value = "100" },

        # Cluster behavior
        { name = "CLUSTER_AUTO_FAILOVER", value = "true" },
        { name = "CLUSTER_AUTO_REBALANCE", value = "true" },
        { name = "CLUSTER_HEARTBEAT_INTERVAL", value = "10" },
        { name = "CLUSTER_HEALTH_CHECK_INTERVAL", value = "30" },
        { name = "CLUSTER_LEADER_LEASE_TTL", value = "30" },

        # Metrics
        { name = "METRICS_PORT", value = "9090" },
        { name = "LOG_LEVEL", value = "INFO" },
      ]
      secrets = [
        { name = "JWT_SECRET", valueFrom = aws_ssm_parameter.jwt_secret.arn },
        { name = "KAGAMI_API_KEY", valueFrom = aws_ssm_parameter.api_key.arn },
        { name = "CSRF_SECRET", valueFrom = aws_ssm_parameter.csrf_secret.arn },
      ]
      command = ["/app/entrypoint.sh"]
      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = "/ecs/${var.app_name}-${var.environment_name}"
          "awslogs-region"        = var.region
          "awslogs-stream-prefix" = "api"
        }
      }
    }
  ])
}

# CSRF Secret
resource "aws_ssm_parameter" "csrf_secret" {
  name  = "/${var.app_name}/${var.environment_name}/CSRF_SECRET"
  type  = "SecureString"
  value = var.csrf_secret
}

# CloudWatch Log Group
resource "aws_cloudwatch_log_group" "app" {
  name              = "/ecs/${var.app_name}-${var.environment_name}"
  retention_in_days = 30
}

resource "aws_ssm_parameter" "jwt_secret" {
  name  = "/${var.app_name}/${var.environment_name}/JWT_SECRET"
  type  = "SecureString"
  value = var.jwt_secret
}

resource "aws_ssm_parameter" "api_key" {
  name  = "/${var.app_name}/${var.environment_name}/KAGAMI_API_KEY"
  type  = "SecureString"
  value = var.kagami_api_key
}

resource "aws_ecs_service" "app" {
  name            = "${var.app_name}-${var.environment_name}"
  cluster         = aws_ecs_cluster.this.id
  task_definition = aws_ecs_task_definition.app.arn
  desired_count   = var.desired_count
  launch_type     = "FARGATE"

  network_configuration {
    subnets         = [for s in aws_subnet.private : s.id]
    security_groups = [aws_security_group.ecs_service.id]
    assign_public_ip = false
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.app.arn
    container_name   = "api"
    container_port   = 8001
  }

  depends_on = [aws_lb_listener.http]
}

# Application Autoscaling for ECS Service
resource "aws_appautoscaling_target" "ecs_service" {
  max_capacity       = 10
  min_capacity       = 2
  resource_id        = "service/${aws_ecs_cluster.this.name}/${aws_ecs_service.app.name}"
  scalable_dimension = "ecs:service:DesiredCount"
  service_namespace  = "ecs"
}

resource "aws_appautoscaling_policy" "cpu_target" {
  name               = "${var.app_name}-${var.environment_name}-cpu-autoscaling"
  policy_type        = "TargetTrackingScaling"
  resource_id        = aws_appautoscaling_target.ecs_service.resource_id
  scalable_dimension = aws_appautoscaling_target.ecs_service.scalable_dimension
  service_namespace  = aws_appautoscaling_target.ecs_service.service_namespace

  target_tracking_scaling_policy_configuration {
    target_value       = 70
    predefined_metric_specification {
      predefined_metric_type = "ECSServiceAverageCPUUtilization"
    }
    scale_in_cooldown  = 60
    scale_out_cooldown = 60
  }
}

resource "aws_appautoscaling_policy" "memory_target" {
  name               = "${var.app_name}-${var.environment_name}-memory-autoscaling"
  policy_type        = "TargetTrackingScaling"
  resource_id        = aws_appautoscaling_target.ecs_service.resource_id
  scalable_dimension = aws_appautoscaling_target.ecs_service.scalable_dimension
  service_namespace  = aws_appautoscaling_target.ecs_service.service_namespace

  target_tracking_scaling_policy_configuration {
    target_value       = 75
    predefined_metric_specification {
      predefined_metric_type = "ECSServiceAverageMemoryUtilization"
    }
    scale_in_cooldown  = 60
    scale_out_cooldown = 60
  }
}
