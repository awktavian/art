output "alb_dns_name" {
  description = "Application Load Balancer DNS name"
  value       = aws_lb.app.dns_name
}

output "service_name" {
  description = "ECS Service name"
  value       = aws_ecs_service.app.name
}
