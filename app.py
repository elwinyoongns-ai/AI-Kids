from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from datetime import datetime, date, timedelta
from models import db, Student, Parent, Center, Course, Teacher, Enrollment, ClassSession, Attendance, Payment
from sqlalchemy import func

app = Flask(__name__)
app.config["SECRET_KEY"] = "ai-kids-education-secret-2024"
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///ai_kids.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db.init_app(app)


@app.context_processor
def inject_globals():
    return {"now": datetime.utcnow()}


def seed_centers():
    data = [
        dict(code="A", name="幼教旗舰中心", target_age="幼儿 (2-6岁)",
             description="幼教(2-6岁)，课程多样，品牌体验。提供全面的早期教育课程，培养孩子思维创造力。"),
        dict(code="B", name="AI+托管成长中心", target_age="小学生 (6-12岁)",
             description="课后托管服务、数字教育、AI作业辅导，让孩子在安全环境下快乐成长。"),
        dict(code="C", name="小学补习+AI学习中心", target_age="小学生 (7-12岁)",
             description="小学各科补习、学习习惯培养、AI辅助个性化学习路径规划。"),
        dict(code="D", name="课程/家长学院", target_age="家长",
             description="家长课程、家庭教育辅导、亲子关系提升，打造家校共育生态。"),
    ]
    for item in data:
        if not Center.query.filter_by(code=item["code"]).first():
            db.session.add(Center(**item))
    db.session.commit()


# ── Dashboard ──────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    total_students = Student.query.filter_by(is_active=True).count()
    total_enrollments = Enrollment.query.filter_by(status="active").count()
    total_courses = Course.query.filter_by(is_active=True).count()
    this_month = date.today().strftime("%Y-%m")
    monthly_revenue = db.session.query(func.sum(Payment.amount)).filter(
        Payment.month == this_month, Payment.status == "paid"
    ).scalar() or 0
    centers = Center.query.order_by(Center.code).all()
    recent_enrollments = Enrollment.query.order_by(Enrollment.created_at.desc()).limit(8).all()
    upcoming_sessions = (
        ClassSession.query
        .filter(ClassSession.date >= date.today())
        .order_by(ClassSession.date)
        .limit(6).all()
    )
    return render_template("index.html",
        total_students=total_students,
        total_enrollments=total_enrollments,
        total_courses=total_courses,
        monthly_revenue=monthly_revenue,
        centers=centers,
        recent_enrollments=recent_enrollments,
        upcoming_sessions=upcoming_sessions,
    )


# ── Students ───────────────────────────────────────────────────────────────────

@app.route("/students")
def students_list():
    q = request.args.get("q", "").strip()
    age_filter = request.args.get("age", "")
    query = Student.query.filter_by(is_active=True)
    if q:
        query = query.filter(Student.name.ilike(f"%{q}%"))
    students = query.order_by(Student.name).all()
    if age_filter == "young":
        students = [s for s in students if s.age is not None and s.age <= 6]
    elif age_filter == "primary":
        students = [s for s in students if s.age is not None and 7 <= s.age <= 12]
    return render_template("students/list.html", students=students, q=q, age_filter=age_filter)


@app.route("/students/add", methods=["GET", "POST"])
def student_add():
    parents = Parent.query.filter_by(is_active=True).order_by(Parent.name).all()
    if request.method == "POST":
        dob_str = request.form.get("dob")
        student = Student(
            name=request.form["name"].strip(),
            gender=request.form.get("gender", ""),
            dob=datetime.strptime(dob_str, "%Y-%m-%d").date() if dob_str else None,
            parent_id=int(request.form["parent_id"]) if request.form.get("parent_id") else None,
            school=request.form.get("school", "").strip() or None,
            grade=request.form.get("grade", "").strip() or None,
            notes=request.form.get("notes", "").strip() or None,
        )
        db.session.add(student)
        db.session.commit()
        flash(f"{student.name} 已成功添加。", "success")
        return redirect(url_for("students_list"))
    return render_template("students/add.html", parents=parents)


@app.route("/students/<int:student_id>")
def student_detail(student_id):
    student = Student.query.get_or_404(student_id)
    enrollments = student.enrollments.order_by(Enrollment.created_at.desc()).all()
    return render_template("students/detail.html", student=student, enrollments=enrollments)


@app.route("/students/<int:student_id>/edit", methods=["GET", "POST"])
def student_edit(student_id):
    student = Student.query.get_or_404(student_id)
    parents = Parent.query.filter_by(is_active=True).order_by(Parent.name).all()
    if request.method == "POST":
        student.name = request.form["name"].strip()
        student.gender = request.form.get("gender", "")
        dob_str = request.form.get("dob")
        student.dob = datetime.strptime(dob_str, "%Y-%m-%d").date() if dob_str else None
        student.parent_id = int(request.form["parent_id"]) if request.form.get("parent_id") else None
        student.school = request.form.get("school", "").strip() or None
        student.grade = request.form.get("grade", "").strip() or None
        student.notes = request.form.get("notes", "").strip() or None
        db.session.commit()
        flash(f"{student.name} 信息已更新。", "success")
        return redirect(url_for("student_detail", student_id=student.id))
    return render_template("students/edit.html", student=student, parents=parents)


@app.route("/students/<int:student_id>/delete", methods=["POST"])
def student_delete(student_id):
    student = Student.query.get_or_404(student_id)
    student.is_active = False
    db.session.commit()
    flash(f"{student.name} 已被移除。", "warning")
    return redirect(url_for("students_list"))


# ── Parents ────────────────────────────────────────────────────────────────────

@app.route("/parents")
def parents_list():
    q = request.args.get("q", "").strip()
    query = Parent.query.filter_by(is_active=True)
    if q:
        query = query.filter(Parent.name.ilike(f"%{q}%") | Parent.phone.ilike(f"%{q}%"))
    parents = query.order_by(Parent.name).all()
    return render_template("parents/list.html", parents=parents, q=q)


@app.route("/parents/add", methods=["GET", "POST"])
def parent_add():
    if request.method == "POST":
        parent = Parent(
            name=request.form["name"].strip(),
            phone=request.form["phone"].strip(),
            email=request.form.get("email", "").strip() or None,
            address=request.form.get("address", "").strip() or None,
            wechat=request.form.get("wechat", "").strip() or None,
            notes=request.form.get("notes", "").strip() or None,
        )
        db.session.add(parent)
        db.session.commit()
        flash(f"{parent.name} 已成功添加。", "success")
        return redirect(url_for("parents_list"))
    return render_template("parents/add.html")


@app.route("/parents/<int:parent_id>")
def parent_detail(parent_id):
    parent = Parent.query.get_or_404(parent_id)
    return render_template("parents/detail.html", parent=parent)


@app.route("/parents/<int:parent_id>/edit", methods=["GET", "POST"])
def parent_edit(parent_id):
    parent = Parent.query.get_or_404(parent_id)
    if request.method == "POST":
        parent.name = request.form["name"].strip()
        parent.phone = request.form["phone"].strip()
        parent.email = request.form.get("email", "").strip() or None
        parent.address = request.form.get("address", "").strip() or None
        parent.wechat = request.form.get("wechat", "").strip() or None
        parent.notes = request.form.get("notes", "").strip() or None
        db.session.commit()
        flash(f"{parent.name} 信息已更新。", "success")
        return redirect(url_for("parent_detail", parent_id=parent.id))
    return render_template("parents/edit.html", parent=parent)


@app.route("/parents/<int:parent_id>/delete", methods=["POST"])
def parent_delete(parent_id):
    parent = Parent.query.get_or_404(parent_id)
    parent.is_active = False
    db.session.commit()
    flash(f"{parent.name} 已被移除。", "warning")
    return redirect(url_for("parents_list"))


# ── Centers ────────────────────────────────────────────────────────────────────

@app.route("/centers")
def centers_list():
    centers = Center.query.order_by(Center.code).all()
    return render_template("centers/list.html", centers=centers)


# ── Courses ────────────────────────────────────────────────────────────────────

@app.route("/courses")
def courses_list():
    center_filter = request.args.get("center", "")
    query = Course.query.filter_by(is_active=True)
    if center_filter:
        query = query.join(Center).filter(Center.code == center_filter)
    courses = query.order_by(Course.name).all()
    centers = Center.query.order_by(Center.code).all()
    return render_template("courses/list.html", courses=courses, centers=centers, center_filter=center_filter)


@app.route("/courses/add", methods=["GET", "POST"])
def course_add():
    centers = Center.query.order_by(Center.code).all()
    if request.method == "POST":
        course = Course(
            name=request.form["name"].strip(),
            center_id=int(request.form["center_id"]),
            description=request.form.get("description", "").strip() or None,
            age_group=request.form.get("age_group", "").strip() or None,
            duration_weeks=int(request.form["duration_weeks"]) if request.form.get("duration_weeks") else None,
            sessions_per_week=int(request.form.get("sessions_per_week", 1)),
            fee=float(request.form.get("fee", 0)),
        )
        db.session.add(course)
        db.session.commit()
        flash(f"课程《{course.name}》已创建。", "success")
        return redirect(url_for("courses_list"))
    return render_template("courses/add.html", centers=centers)


@app.route("/courses/<int:course_id>")
def course_detail(course_id):
    course = Course.query.get_or_404(course_id)
    enrollments = course.enrollments.filter_by(status="active").all()
    sessions = course.sessions.order_by(ClassSession.date.desc()).limit(10).all()
    return render_template("courses/detail.html", course=course, enrollments=enrollments, sessions=sessions)


@app.route("/courses/<int:course_id>/edit", methods=["GET", "POST"])
def course_edit(course_id):
    course = Course.query.get_or_404(course_id)
    centers = Center.query.order_by(Center.code).all()
    if request.method == "POST":
        course.name = request.form["name"].strip()
        course.center_id = int(request.form["center_id"])
        course.description = request.form.get("description", "").strip() or None
        course.age_group = request.form.get("age_group", "").strip() or None
        course.duration_weeks = int(request.form["duration_weeks"]) if request.form.get("duration_weeks") else None
        course.sessions_per_week = int(request.form.get("sessions_per_week", 1))
        course.fee = float(request.form.get("fee", 0))
        db.session.commit()
        flash(f"课程《{course.name}》已更新。", "success")
        return redirect(url_for("course_detail", course_id=course.id))
    return render_template("courses/edit.html", course=course, centers=centers)


# ── Teachers ───────────────────────────────────────────────────────────────────

@app.route("/teachers")
def teachers_list():
    teachers = Teacher.query.filter_by(is_active=True).order_by(Teacher.name).all()
    return render_template("teachers/list.html", teachers=teachers)


@app.route("/teachers/add", methods=["GET", "POST"])
def teacher_add():
    if request.method == "POST":
        teacher = Teacher(
            name=request.form["name"].strip(),
            phone=request.form.get("phone", "").strip() or None,
            email=request.form.get("email", "").strip() or None,
            specialty=request.form.get("specialty", "").strip() or None,
        )
        db.session.add(teacher)
        db.session.commit()
        flash(f"{teacher.name} 已添加为教师。", "success")
        return redirect(url_for("teachers_list"))
    return render_template("teachers/add.html")


@app.route("/teachers/<int:teacher_id>/edit", methods=["GET", "POST"])
def teacher_edit(teacher_id):
    teacher = Teacher.query.get_or_404(teacher_id)
    if request.method == "POST":
        teacher.name = request.form["name"].strip()
        teacher.phone = request.form.get("phone", "").strip() or None
        teacher.email = request.form.get("email", "").strip() or None
        teacher.specialty = request.form.get("specialty", "").strip() or None
        db.session.commit()
        flash(f"{teacher.name} 信息已更新。", "success")
        return redirect(url_for("teachers_list"))
    return render_template("teachers/edit.html", teacher=teacher)


@app.route("/teachers/<int:teacher_id>/delete", methods=["POST"])
def teacher_delete(teacher_id):
    teacher = Teacher.query.get_or_404(teacher_id)
    teacher.is_active = False
    db.session.commit()
    flash(f"{teacher.name} 已被移除。", "warning")
    return redirect(url_for("teachers_list"))


# ── Enrollments ────────────────────────────────────────────────────────────────

@app.route("/enrollments")
def enrollments_list():
    status_filter = request.args.get("status", "active")
    query = Enrollment.query
    if status_filter:
        query = query.filter_by(status=status_filter)
    enrollments = query.order_by(Enrollment.created_at.desc()).all()
    return render_template("enrollments/list.html", enrollments=enrollments, status_filter=status_filter)


@app.route("/enrollments/add", methods=["GET", "POST"])
def enrollment_add():
    students = Student.query.filter_by(is_active=True).order_by(Student.name).all()
    courses = Course.query.filter_by(is_active=True).order_by(Course.name).all()
    if request.method == "POST":
        student_id = int(request.form["student_id"])
        course_id = int(request.form["course_id"])
        existing = Enrollment.query.filter_by(student_id=student_id, course_id=course_id).first()
        if existing:
            flash("该学生已报名此课程。", "warning")
            return redirect(url_for("enrollments_list"))
        start_str = request.form.get("start_date")
        enrollment = Enrollment(
            student_id=student_id,
            course_id=course_id,
            start_date=datetime.strptime(start_str, "%Y-%m-%d").date() if start_str else date.today(),
            notes=request.form.get("notes", "").strip() or None,
        )
        db.session.add(enrollment)
        db.session.commit()
        flash("报名成功！", "success")
        return redirect(url_for("enrollments_list"))
    return render_template("enrollments/add.html", students=students, courses=courses)


@app.route("/enrollments/<int:enrollment_id>/status", methods=["POST"])
def enrollment_status(enrollment_id):
    enrollment = Enrollment.query.get_or_404(enrollment_id)
    enrollment.status = request.form["status"]
    db.session.commit()
    flash("报名状态已更新。", "success")
    return redirect(request.referrer or url_for("enrollments_list"))


# ── Sessions ───────────────────────────────────────────────────────────────────

@app.route("/sessions")
def sessions_list():
    course_filter = request.args.get("course", "")
    query = ClassSession.query
    if course_filter:
        query = query.filter(ClassSession.course_id == int(course_filter))
    class_sessions = query.order_by(ClassSession.date.desc()).limit(50).all()
    courses = Course.query.filter_by(is_active=True).order_by(Course.name).all()
    return render_template("sessions/list.html", class_sessions=class_sessions, courses=courses, course_filter=course_filter)


@app.route("/sessions/add", methods=["GET", "POST"])
def session_add():
    courses = Course.query.filter_by(is_active=True).order_by(Course.name).all()
    teachers = Teacher.query.filter_by(is_active=True).order_by(Teacher.name).all()
    if request.method == "POST":
        date_str = request.form["date"]
        cs = ClassSession(
            course_id=int(request.form["course_id"]),
            teacher_id=int(request.form["teacher_id"]) if request.form.get("teacher_id") else None,
            date=datetime.strptime(date_str, "%Y-%m-%d").date(),
            start_time=request.form.get("start_time", "").strip() or None,
            end_time=request.form.get("end_time", "").strip() or None,
            topic=request.form.get("topic", "").strip() or None,
            notes=request.form.get("notes", "").strip() or None,
        )
        db.session.add(cs)
        db.session.flush()
        enrolled = Enrollment.query.filter_by(course_id=cs.course_id, status="active").all()
        for e in enrolled:
            db.session.add(Attendance(student_id=e.student_id, session_id=cs.id, present=False))
        db.session.commit()
        flash(f"课程安排已创建，共 {len(enrolled)} 名学生。", "success")
        return redirect(url_for("session_attendance", session_id=cs.id))
    return render_template("sessions/add.html", courses=courses, teachers=teachers, today=date.today().isoformat())


@app.route("/sessions/<int:session_id>/attendance", methods=["GET", "POST"])
def session_attendance(session_id):
    cs = ClassSession.query.get_or_404(session_id)
    if request.method == "POST":
        present_ids = set(int(x) for x in request.form.getlist("present"))
        for record in cs.attendance_records.all():
            record.present = record.student_id in present_ids
        db.session.commit()
        flash("出勤记录已保存。", "success")
        return redirect(url_for("sessions_list"))
    records = cs.attendance_records.join(Student).order_by(Student.name).all()
    existing_ids = {r.student_id for r in records}
    missing = Enrollment.query.filter_by(course_id=cs.course_id, status="active").filter(
        ~Enrollment.student_id.in_(existing_ids)
    ).all()
    for e in missing:
        db.session.add(Attendance(student_id=e.student_id, session_id=session_id, present=False))
    if missing:
        db.session.commit()
        records = cs.attendance_records.join(Student).order_by(Student.name).all()
    return render_template("sessions/attendance.html", cs=cs, records=records)


@app.route("/sessions/<int:session_id>/delete", methods=["POST"])
def session_delete(session_id):
    cs = ClassSession.query.get_or_404(session_id)
    Attendance.query.filter_by(session_id=session_id).delete()
    db.session.delete(cs)
    db.session.commit()
    flash("课程已删除。", "warning")
    return redirect(url_for("sessions_list"))


# ── Payments ───────────────────────────────────────────────────────────────────

@app.route("/payments")
def payments_list():
    month_filter = request.args.get("month", date.today().strftime("%Y-%m"))
    status_filter = request.args.get("status", "")
    query = Payment.query
    if month_filter:
        query = query.filter_by(month=month_filter)
    if status_filter:
        query = query.filter_by(status=status_filter)
    payments = query.order_by(Payment.paid_date.desc()).all()
    total = sum(p.amount for p in payments if p.status == "paid")
    return render_template("payments/list.html", payments=payments, month_filter=month_filter,
                           status_filter=status_filter, total=total)


@app.route("/payments/add", methods=["GET", "POST"])
def payment_add():
    enrollments = (
        Enrollment.query.filter_by(status="active")
        .join(Student).join(Course)
        .order_by(Student.name).all()
    )
    if request.method == "POST":
        paid_str = request.form.get("paid_date")
        payment = Payment(
            enrollment_id=int(request.form["enrollment_id"]),
            amount=float(request.form["amount"]),
            paid_date=datetime.strptime(paid_str, "%Y-%m-%d").date() if paid_str else date.today(),
            method=request.form.get("method", "现金"),
            month=request.form.get("month", date.today().strftime("%Y-%m")),
            status=request.form.get("status", "paid"),
            notes=request.form.get("notes", "").strip() or None,
        )
        db.session.add(payment)
        db.session.commit()
        flash(f"收费记录已保存，金额 RM{payment.amount:.2f}。", "success")
        return redirect(url_for("payments_list"))
    return render_template("payments/add.html", enrollments=enrollments, today=date.today().isoformat(),
                           this_month=date.today().strftime("%Y-%m"))


# ── Reports ────────────────────────────────────────────────────────────────────

@app.route("/reports")
def reports():
    today = date.today()
    months = [(today.replace(day=1) - timedelta(days=30 * i)).strftime("%Y-%m") for i in range(5, -1, -1)]
    revenue_data = []
    for m in months:
        amt = db.session.query(func.sum(Payment.amount)).filter(
            Payment.month == m, Payment.status == "paid"
        ).scalar() or 0
        revenue_data.append({"month": m, "amount": float(amt)})

    students = Student.query.filter_by(is_active=True).all()
    age_groups = {"幼儿 (2-6岁)": 0, "小学生 (7-12岁)": 0, "其他": 0}
    for s in students:
        age_groups[s.age_group] = age_groups.get(s.age_group, 0) + 1

    center_enrollments = (
        db.session.query(Center.name, Center.code, func.count(Enrollment.id))
        .join(Course, Course.center_id == Center.id)
        .join(Enrollment, Enrollment.course_id == Course.id)
        .filter(Enrollment.status == "active")
        .group_by(Center.id).all()
    )

    top_courses = (
        db.session.query(Course.name, func.count(Enrollment.id).label("cnt"))
        .join(Enrollment).filter(Enrollment.status == "active")
        .group_by(Course.id)
        .order_by(func.count(Enrollment.id).desc())
        .limit(5).all()
    )

    total_revenue = db.session.query(func.sum(Payment.amount)).filter_by(status="paid").scalar() or 0
    pending_count = Payment.query.filter_by(status="pending").count()

    return render_template("reports/index.html",
        revenue_data=revenue_data,
        age_groups=age_groups,
        center_enrollments=center_enrollments,
        top_courses=top_courses,
        total_revenue=total_revenue,
        pending_count=pending_count,
    )


# ── API ────────────────────────────────────────────────────────────────────────

@app.route("/api/toggle-attendance", methods=["POST"])
def toggle_attendance():
    data = request.get_json()
    record = Attendance.query.filter_by(
        student_id=data["student_id"], session_id=data["session_id"]
    ).first()
    if not record:
        return jsonify({"error": "Not found"}), 404
    record.present = not record.present
    db.session.commit()
    return jsonify({"present": record.present})


if __name__ == "__main__":
    with app.app_context():
        db.create_all()
        seed_centers()
    app.run(host="0.0.0.0", port=5000, debug=True)
