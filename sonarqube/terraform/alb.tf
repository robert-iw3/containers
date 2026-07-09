resource "aws_lb" "alb" {
  name               = "sonarqube-load-balancer"
  load_balancer_type = "application"
  security_groups    = [aws_security_group._____________.id]
  subnets            = [aws_subnet._____________.id, aws_subnet._____________.id]
}

resource "aws_lb_target_group" "sonarqube_web" {
  name     = "sonarqube-web"
  port     = 9000
  protocol = "HTTP"
  vpc_id   = aws_vpc._____________.id
  health_check {
    protocol = "HTTP"
    path     = "/"
    matcher  = "200"
  }
}

resource "aws_lb_target_group_attachment" "sonarqube_web" {
  target_group_arn = aws_lb_target_group.sonarqube_web.arn
  target_id        = aws_instance.nessus_instance.id
  lifecycle {
    create_before_destroy = true
  }
}


resource "aws_lb_listener" "http" {
  load_balancer_arn = aws_lb.alb.arn
  port              = "9000"
  protocol          = "HTTP"
  certificate_arn   = aws_acm_certificate.fqdn.arn

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.sonarqube_web.arn
  }
}
