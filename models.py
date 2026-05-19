from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, date

db = SQLAlchemy()


class Parent(db.Model):
    __tablename__ = "parents"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(30), nullable=False)
    email = db.Column(db.String(200))
    address = db.Column(db.String(300))
    wechat = db.Column(db.String(100))
    notes = db.Column(db.Text)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    students = db.relationship("Student", back_populates="parent", lazy="dynamic")


class Student(db.Model):
    __tablename__ = "students"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    dob = db.Column(db.Date)
    gender = db.Column(db.String(10))
    parent_id = db.Column(db.Integer, db.ForeignKey("parents.id"))
    school = db.Column(db.String(200))
    grade = db.Column(db.String(50))
    notes = db.Column(db.Text)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    parent = db.relationship("Parent", back_populates="students")
    enrollments = db.relationship("Enrollment", back_populates="student", lazy="dynamic")

    @property
    def age(self):
        if not self.dob:
            return None
        today = date.today()
        return today.year - self.dob.year - ((today.month, today.day) < (self.dob.month, self.dob.day))

    @property
    def age_group(self):
        a = self.age
        if a is None:
            return "未知"
        if a <= 6:
            return "幼儿 (2-6岁)"
        if a <= 12:
            return "小学生 (7-12岁)"
        return "其他"


class Center(db.Model):
    __tablename__ = "centers"
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(10), nullable=False, unique=True)
    name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    target_age = db.Column(db.String(100))
    courses = db.relationship("Course", back_populates="center", lazy="dynamic")


class Course(db.Model):
    __tablename__ = "courses"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    center_id = db.Column(db.Integer, db.ForeignKey("centers.id"), nullable=False)
    description = db.Column(db.Text)
    age_group = db.Column(db.String(100))
    duration_weeks = db.Column(db.Integer)
    sessions_per_week = db.Column(db.Integer, default=1)
    fee = db.Column(db.Float, default=0)
    is_active = db.Column(db.Boolean, default=True)
    center = db.relationship("Center", back_populates="courses")
    enrollments = db.relationship("Enrollment", back_populates="course", lazy="dynamic")
    sessions = db.relationship("ClassSession", back_populates="course", lazy="dynamic")


class Teacher(db.Model):
    __tablename__ = "teachers"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(30))
    email = db.Column(db.String(200))
    specialty = db.Column(db.String(200))
    is_active = db.Column(db.Boolean, default=True)
    sessions = db.relationship("ClassSession", back_populates="teacher", lazy="dynamic")


class Enrollment(db.Model):
    __tablename__ = "enrollments"
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("students.id"), nullable=False)
    course_id = db.Column(db.Integer, db.ForeignKey("courses.id"), nullable=False)
    start_date = db.Column(db.Date, default=date.today)
    end_date = db.Column(db.Date)
    status = db.Column(db.String(20), default="active")
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    student = db.relationship("Student", back_populates="enrollments")
    course = db.relationship("Course", back_populates="enrollments")
    payments = db.relationship("Payment", back_populates="enrollment", lazy="dynamic")

    __table_args__ = (
        db.UniqueConstraint("student_id", "course_id", name="uq_student_course"),
    )


class ClassSession(db.Model):
    __tablename__ = "class_sessions"
    id = db.Column(db.Integer, primary_key=True)
    course_id = db.Column(db.Integer, db.ForeignKey("courses.id"), nullable=False)
    teacher_id = db.Column(db.Integer, db.ForeignKey("teachers.id"))
    date = db.Column(db.Date, nullable=False)
    start_time = db.Column(db.String(10))
    end_time = db.Column(db.String(10))
    topic = db.Column(db.String(300))
    notes = db.Column(db.Text)
    course = db.relationship("Course", back_populates="sessions")
    teacher = db.relationship("Teacher", back_populates="sessions")
    attendance_records = db.relationship("Attendance", back_populates="session", lazy="dynamic")

    def present_count(self):
        return self.attendance_records.filter_by(present=True).count()

    def total_count(self):
        return self.attendance_records.count()


class Attendance(db.Model):
    __tablename__ = "attendance"
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("students.id"), nullable=False)
    session_id = db.Column(db.Integer, db.ForeignKey("class_sessions.id"), nullable=False)
    present = db.Column(db.Boolean, default=False)
    notes = db.Column(db.String(300))
    recorded_at = db.Column(db.DateTime, default=datetime.utcnow)
    student = db.relationship("Student")
    session = db.relationship("ClassSession", back_populates="attendance_records")

    __table_args__ = (
        db.UniqueConstraint("student_id", "session_id", name="uq_student_session"),
    )


class Payment(db.Model):
    __tablename__ = "payments"
    id = db.Column(db.Integer, primary_key=True)
    enrollment_id = db.Column(db.Integer, db.ForeignKey("enrollments.id"), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    paid_date = db.Column(db.Date, default=date.today)
    method = db.Column(db.String(50))
    month = db.Column(db.String(7))
    status = db.Column(db.String(20), default="paid")
    notes = db.Column(db.String(300))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    enrollment = db.relationship("Enrollment", back_populates="payments")
