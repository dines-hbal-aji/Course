from flask import Flask, render_template, redirect, url_for, request, flash, jsonify, session, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from datetime import datetime, date
import os
import json

app = Flask(__name__)
app.config['SECRET_KEY'] = 'cms-secret-key-2024-madurai-college'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///cms.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50MB

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.login_message_category = 'info'

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs('uploads/assignments', exist_ok=True)
os.makedirs('uploads/materials', exist_ok=True)
os.makedirs('uploads/submissions', exist_ok=True)

ALLOWED_EXTENSIONS = {'pdf', 'doc', 'docx', 'ppt', 'pptx', 'mp4', 'png', 'jpg', 'jpeg', 'xlsx', 'zip'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# ============================================================
# MODELS
# ============================================================

class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(20), nullable=False, default='student')  # admin/faculty/student
    phone = db.Column(db.String(20))
    department = db.Column(db.String(100))
    profile_pic = db.Column(db.String(200), default='default.png')
    is_active_account = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    courses_taught = db.relationship('Course', backref='faculty', lazy=True, foreign_keys='Course.faculty_id')
    enrollments = db.relationship('Enrollment', backref='student', lazy=True, foreign_keys='Enrollment.student_id')

class Course(db.Model):
    __tablename__ = 'courses'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    code = db.Column(db.String(20), unique=True, nullable=False)
    description = db.Column(db.Text)
    credits = db.Column(db.Integer, default=3)
    semester = db.Column(db.Integer, default=1)
    department = db.Column(db.String(100))
    faculty_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    max_students = db.Column(db.Integer, default=60)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    enrollments = db.relationship('Enrollment', backref='course', lazy=True)
    assignments = db.relationship('Assignment', backref='course', lazy=True)
    materials = db.relationship('Material', backref='course', lazy=True)
    exams = db.relationship('Exam', backref='course', lazy=True)

class Enrollment(db.Model):
    __tablename__ = 'enrollments'
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    course_id = db.Column(db.Integer, db.ForeignKey('courses.id'), nullable=False)
    status = db.Column(db.String(20), default='pending')  # pending/approved/rejected
    enrolled_at = db.Column(db.DateTime, default=datetime.utcnow)
    approved_at = db.Column(db.DateTime)

class Assignment(db.Model):
    __tablename__ = 'assignments'
    id = db.Column(db.Integer, primary_key=True)
    course_id = db.Column(db.Integer, db.ForeignKey('courses.id'), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    due_date = db.Column(db.DateTime)
    max_marks = db.Column(db.Integer, default=100)
    file_path = db.Column(db.String(300))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    submissions = db.relationship('Submission', backref='assignment', lazy=True)

class Submission(db.Model):
    __tablename__ = 'submissions'
    id = db.Column(db.Integer, primary_key=True)
    assignment_id = db.Column(db.Integer, db.ForeignKey('assignments.id'), nullable=False)
    student_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    file_path = db.Column(db.String(300))
    grade = db.Column(db.Float)
    feedback = db.Column(db.Text)
    submitted_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_late = db.Column(db.Boolean, default=False)

    student = db.relationship('User', foreign_keys=[student_id])

class Material(db.Model):
    __tablename__ = 'materials'
    id = db.Column(db.Integer, primary_key=True)
    course_id = db.Column(db.Integer, db.ForeignKey('courses.id'), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    file_path = db.Column(db.String(300))
    file_type = db.Column(db.String(20))
    download_count = db.Column(db.Integer, default=0)
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)

class Exam(db.Model):
    __tablename__ = 'exams'
    id = db.Column(db.Integer, primary_key=True)
    course_id = db.Column(db.Integer, db.ForeignKey('courses.id'), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    exam_date = db.Column(db.DateTime)
    duration = db.Column(db.Integer, default=180)  # minutes
    max_marks = db.Column(db.Integer, default=100)
    exam_type = db.Column(db.String(50), default='midterm')  # midterm/final/quiz
    venue = db.Column(db.String(100))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    results = db.relationship('Result', backref='exam', lazy=True)

class Result(db.Model):
    __tablename__ = 'results'
    id = db.Column(db.Integer, primary_key=True)
    exam_id = db.Column(db.Integer, db.ForeignKey('exams.id'), nullable=False)
    student_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    marks_obtained = db.Column(db.Float, default=0)
    total_marks = db.Column(db.Integer, default=100)
    grade_letter = db.Column(db.String(5))
    remarks = db.Column(db.Text)
    published = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    student = db.relationship('User', foreign_keys=[student_id])

class Announcement(db.Model):
    __tablename__ = 'announcements'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text, nullable=False)
    author_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    target_role = db.Column(db.String(20), default='all')  # all/student/faculty
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    author = db.relationship('User', foreign_keys=[author_id])

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# ============================================================
# UTILITY
# ============================================================

def get_grade_letter(percentage):
    if percentage >= 90: return 'O'
    elif percentage >= 80: return 'A+'
    elif percentage >= 70: return 'A'
    elif percentage >= 60: return 'B+'
    elif percentage >= 50: return 'B'
    elif percentage >= 40: return 'C'
    else: return 'F'

# ============================================================
# ============================================================
# AUTH ROUTES
# ============================================================

@app.context_processor
def inject_now():
    return {'now': datetime.utcnow().date()}


@app.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for(f'{current_user.role}_dashboard'))
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for(f'{current_user.role}_dashboard'))
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        user = User.query.filter_by(email=email).first()
        if user and check_password_hash(user.password, password):
            login_user(user)
            flash(f'Welcome back, {user.name}! 🎉', 'success')
            return redirect(url_for(f'{user.role}_dashboard'))
        flash('Invalid email or password. Please try again.', 'danger')
    return render_template('auth/login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for(f'{current_user.role}_dashboard'))
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        password = request.form.get('password')
        role = request.form.get('role', 'student')
        department = request.form.get('department', '')
        phone = request.form.get('phone', '')

        if User.query.filter_by(email=email).first():
            flash('Email already registered. Please login.', 'warning')
            return redirect(url_for('register'))

        hashed_pw = generate_password_hash(password)
        user = User(name=name, email=email, password=hashed_pw, role=role,
                    department=department, phone=phone)
        db.session.add(user)
        db.session.commit()
        flash('Registration successful! Please login.', 'success')
        return redirect(url_for('login'))
    return render_template('auth/register.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out successfully.', 'info')
    return redirect(url_for('login'))

# ============================================================
# ADMIN ROUTES
# ============================================================

@app.route('/admin/dashboard')
@login_required
def admin_dashboard():
    if current_user.role != 'admin':
        flash('Access denied!', 'danger')
        return redirect(url_for('index'))

    total_students = User.query.filter_by(role='student').count()
    total_faculty = User.query.filter_by(role='faculty').count()
    total_courses = Course.query.count()
    pending_enrollments = Enrollment.query.filter_by(status='pending').count()
    active_courses = Course.query.filter_by(is_active=True).count()
    total_assignments = Assignment.query.count()
    total_exams = Exam.query.count()

    recent_enrollments = db.session.query(Enrollment, User, Course)\
        .join(User, Enrollment.student_id == User.id)\
        .join(Course, Enrollment.course_id == Course.id)\
        .order_by(Enrollment.enrolled_at.desc()).limit(5).all()

    announcements = Announcement.query.order_by(Announcement.created_at.desc()).limit(3).all()

    # Course enrollment data for chart
    courses = Course.query.all()
    course_labels = [c.name[:20] for c in courses[:8]]
    course_data = [Enrollment.query.filter_by(course_id=c.id, status='approved').count() for c in courses[:8]]

    # Monthly enrollment for line chart (simulate)
    monthly_data = [12, 19, 15, 25, 22, 30, 28, 35, 32, 40, 38, 45]

    return render_template('admin/dashboard.html',
        total_students=total_students, total_faculty=total_faculty,
        total_courses=total_courses, pending_enrollments=pending_enrollments,
        active_courses=active_courses, total_assignments=total_assignments,
        total_exams=total_exams, recent_enrollments=recent_enrollments,
        announcements=announcements, course_labels=json.dumps(course_labels),
        course_data=json.dumps(course_data), monthly_data=json.dumps(monthly_data))

@app.route('/admin/courses')
@login_required
def admin_courses():
    if current_user.role != 'admin': return redirect(url_for('index'))
    courses = db.session.query(Course, User)\
        .outerjoin(User, Course.faculty_id == User.id)\
        .order_by(Course.created_at.desc()).all()
    faculty_list = User.query.filter_by(role='faculty').all()
    return render_template('admin/courses.html', courses=courses, faculty_list=faculty_list)

@app.route('/admin/courses/add', methods=['POST'])
@login_required
def admin_add_course():
    if current_user.role != 'admin': return redirect(url_for('index'))
    course = Course(
        name=request.form.get('name'),
        code=request.form.get('code'),
        description=request.form.get('description'),
        credits=int(request.form.get('credits', 3)),
        semester=int(request.form.get('semester', 1)),
        department=request.form.get('department'),
        faculty_id=request.form.get('faculty_id') or None,
        max_students=int(request.form.get('max_students', 60))
    )
    db.session.add(course)
    db.session.commit()
    flash('Course added successfully! ✅', 'success')
    return redirect(url_for('admin_courses'))

@app.route('/admin/courses/<int:id>/edit', methods=['POST'])
@login_required
def admin_edit_course(id):
    if current_user.role != 'admin': return redirect(url_for('index'))
    course = Course.query.get_or_404(id)
    course.name = request.form.get('name')
    course.code = request.form.get('code')
    course.description = request.form.get('description')
    course.credits = int(request.form.get('credits', 3))
    course.semester = int(request.form.get('semester', 1))
    course.department = request.form.get('department')
    course.faculty_id = request.form.get('faculty_id') or None
    course.max_students = int(request.form.get('max_students', 60))
    db.session.commit()
    flash('Course updated successfully! ✅', 'success')
    return redirect(url_for('admin_courses'))

@app.route('/admin/courses/<int:id>/delete', methods=['POST'])
@login_required
def admin_delete_course(id):
    if current_user.role != 'admin': return redirect(url_for('index'))
    course = Course.query.get_or_404(id)
    # Manually delete dependencies
    Enrollment.query.filter_by(course_id=id).delete()
    Material.query.filter_by(course_id=id).delete()
    assignments = Assignment.query.filter_by(course_id=id).all()
    for a in assignments:
        Submission.query.filter_by(assignment_id=a.id).delete()
        db.session.delete(a)
    exams = Exam.query.filter_by(course_id=id).all()
    for e in exams:
        Result.query.filter_by(exam_id=e.id).delete()
        db.session.delete(e)
    
    db.session.delete(course)
    db.session.commit()
    flash('Course deleted successfully!', 'success')
    return redirect(url_for('admin_courses'))

@app.route('/admin/users')
@login_required
def admin_users():
    if current_user.role != 'admin': return redirect(url_for('index'))
    role_filter = request.args.get('role', 'all')
    if role_filter != 'all':
        users = User.query.filter_by(role=role_filter).order_by(User.created_at.desc()).all()
    else:
        users = User.query.order_by(User.created_at.desc()).all()
    return render_template('admin/users.html', users=users, role_filter=role_filter)

@app.route('/admin/users/<int:id>/toggle', methods=['POST'])
@login_required
def admin_toggle_user(id):
    if current_user.role != 'admin': return redirect(url_for('index'))
    user = User.query.get_or_404(id)
    user.is_active_account = not user.is_active_account
    db.session.commit()
    status = 'activated' if user.is_active_account else 'deactivated'
    flash(f'User {status} successfully!', 'success')
    return redirect(url_for('admin_users'))

@app.route('/admin/enrollments')
@login_required
def admin_enrollments():
    if current_user.role != 'admin': return redirect(url_for('index'))
    status_filter = request.args.get('status', 'pending')
    enrollments = db.session.query(Enrollment, User, Course)\
        .join(User, Enrollment.student_id == User.id)\
        .join(Course, Enrollment.course_id == Course.id)
    if status_filter != 'all':
        enrollments = enrollments.filter(Enrollment.status == status_filter)
    enrollments = enrollments.order_by(Enrollment.enrolled_at.desc()).all()
    return render_template('admin/enrollments.html', enrollments=enrollments, status_filter=status_filter)

@app.route('/admin/enrollments/<int:id>/approve', methods=['POST'])
@login_required
def admin_approve_enrollment(id):
    if current_user.role != 'admin': return redirect(url_for('index'))
    enroll = Enrollment.query.get_or_404(id)
    enroll.status = 'approved'
    enroll.approved_at = datetime.utcnow()
    db.session.commit()
    flash('Enrollment approved! ✅', 'success')
    return redirect(url_for('admin_enrollments'))

@app.route('/admin/enrollments/<int:id>/reject', methods=['POST'])
@login_required
def admin_reject_enrollment(id):
    if current_user.role != 'admin': return redirect(url_for('index'))
    enroll = Enrollment.query.get_or_404(id)
    enroll.status = 'rejected'
    db.session.commit()
    flash('Enrollment rejected.', 'warning')
    return redirect(url_for('admin_enrollments'))

@app.route('/admin/announcements', methods=['GET', 'POST'])
@login_required
def admin_announcements():
    if current_user.role != 'admin': return redirect(url_for('index'))
    if request.method == 'POST':
        ann = Announcement(
            title=request.form.get('title'),
            content=request.form.get('content'),
            author_id=current_user.id,
            target_role=request.form.get('target_role', 'all')
        )
        db.session.add(ann)
        db.session.commit()
        flash('Announcement posted! 📢', 'success')
    announcements = Announcement.query.order_by(Announcement.created_at.desc()).all()
    return render_template('admin/announcements.html', announcements=announcements)

@app.route('/admin/announcements/<int:id>/delete', methods=['POST'])
@login_required
def admin_delete_announcement(id):
    if current_user.role != 'admin': return redirect(url_for('index'))
    ann = Announcement.query.get_or_404(id)
    db.session.delete(ann)
    db.session.commit()
    flash('Announcement deleted.', 'success')
    return redirect(url_for('admin_announcements'))

@app.route('/admin/reports')
@login_required
def admin_reports():
    if current_user.role != 'admin': return redirect(url_for('index'))
    courses = Course.query.all()
    report_data = []
    for c in courses:
        enrolled = Enrollment.query.filter_by(course_id=c.id, status='approved').count()
        assignments = Assignment.query.filter_by(course_id=c.id).count()
        exams = Exam.query.filter_by(course_id=c.id).count()
        report_data.append({'course': c, 'enrolled': enrolled, 'assignments': assignments, 'exams': exams})
    return render_template('admin/reports.html', report_data=report_data)

# ============================================================
# FACULTY ROUTES
# ============================================================

@app.route('/faculty/dashboard')
@login_required
def faculty_dashboard():
    if current_user.role != 'faculty': return redirect(url_for('index'))
    my_courses = Course.query.filter_by(faculty_id=current_user.id).all()
    total_students = 0
    for c in my_courses:
        total_students += Enrollment.query.filter_by(course_id=c.id, status='approved').count()
    total_assignments = sum(Assignment.query.filter_by(course_id=c.id).count() for c in my_courses)
    pending_submissions = 0
    for c in my_courses:
        for a in c.assignments:
            pending_submissions += Submission.query.filter_by(assignment_id=a.id, grade=None).count()

    upcoming_exams = []
    for c in my_courses:
        exams = Exam.query.filter(Exam.course_id == c.id, Exam.exam_date >= datetime.utcnow()).all()
        upcoming_exams.extend(exams)

    announcements = Announcement.query.filter(
        Announcement.target_role.in_(['all', 'faculty'])
    ).order_by(Announcement.created_at.desc()).limit(3).all()

    return render_template('faculty/dashboard.html',
        my_courses=my_courses, total_students=total_students,
        total_assignments=total_assignments, pending_submissions=pending_submissions,
        upcoming_exams=upcoming_exams[:5], announcements=announcements)

@app.route('/faculty/courses')
@login_required
def faculty_courses():
    if current_user.role != 'faculty': return redirect(url_for('index'))
    courses = Course.query.filter_by(faculty_id=current_user.id).all()
    return render_template('faculty/courses.html', courses=courses)

@app.route('/faculty/courses/<int:course_id>')
@login_required
def faculty_course_detail(course_id):
    if current_user.role != 'faculty': return redirect(url_for('index'))
    course = Course.query.get_or_404(course_id)
    if course.faculty_id != current_user.id: return redirect(url_for('faculty_courses'))
    students = db.session.query(User, Enrollment)\
        .join(Enrollment, User.id == Enrollment.student_id)\
        .filter(Enrollment.course_id == course_id, Enrollment.status == 'approved').all()
    assignments = Assignment.query.filter_by(course_id=course_id).all()
    materials = Material.query.filter_by(course_id=course_id).all()
    exams = Exam.query.filter_by(course_id=course_id).all()
    return render_template('faculty/course_detail.html',
        course=course, students=students, assignments=assignments, materials=materials, exams=exams)

@app.route('/faculty/assignments/add', methods=['POST'])
@login_required
def faculty_add_assignment():
    if current_user.role != 'faculty': return redirect(url_for('index'))
    file_path = None
    if 'file' in request.files and request.files['file'].filename:
        f = request.files['file']
        if allowed_file(f.filename):
            filename = secure_filename(f.filename)
            f.save(os.path.join('uploads/assignments', filename))
            file_path = filename

    due_date = None
    if request.form.get('due_date'):
        try:
            due_date = datetime.strptime(request.form.get('due_date'), '%Y-%m-%dT%H:%M')
        except:
            pass

    assignment = Assignment(
        course_id=int(request.form.get('course_id')),
        title=request.form.get('title'),
        description=request.form.get('description'),
        due_date=due_date,
        max_marks=int(request.form.get('max_marks', 100)),
        file_path=file_path
    )
    db.session.add(assignment)
    db.session.commit()
    flash('Assignment created successfully! 📝', 'success')
    return redirect(url_for('faculty_course_detail', course_id=assignment.course_id))

@app.route('/faculty/materials/add', methods=['POST'])
@login_required
def faculty_add_material():
    if current_user.role != 'faculty': return redirect(url_for('index'))
    file_path = None
    file_type = 'document'
    if 'file' in request.files and request.files['file'].filename:
        f = request.files['file']
        if allowed_file(f.filename):
            filename = secure_filename(f.filename)
            f.save(os.path.join('uploads/materials', filename))
            file_path = filename
            ext = filename.rsplit('.', 1)[1].lower()
            if ext in ['mp4', 'avi', 'mkv']: file_type = 'video'
            elif ext in ['pdf']: file_type = 'pdf'
            elif ext in ['ppt', 'pptx']: file_type = 'presentation'
            elif ext in ['jpg', 'jpeg', 'png']: file_type = 'image'

    material = Material(
        course_id=int(request.form.get('course_id')),
        title=request.form.get('title'),
        description=request.form.get('description'),
        file_path=file_path,
        file_type=file_type
    )
    db.session.add(material)
    db.session.commit()
    flash('Study material uploaded successfully! 📁', 'success')
    return redirect(url_for('faculty_course_detail', course_id=material.course_id))

@app.route('/faculty/exams/add', methods=['POST'])
@login_required
def faculty_add_exam():
    if current_user.role != 'faculty': return redirect(url_for('index'))
    exam_date = None
    if request.form.get('exam_date'):
        try:
            exam_date = datetime.strptime(request.form.get('exam_date'), '%Y-%m-%dT%H:%M')
        except:
            pass

    exam = Exam(
        course_id=int(request.form.get('course_id')),
        title=request.form.get('title'),
        exam_date=exam_date,
        duration=int(request.form.get('duration', 180)),
        max_marks=int(request.form.get('max_marks', 100)),
        exam_type=request.form.get('exam_type', 'midterm'),
        venue=request.form.get('venue')
    )
    db.session.add(exam)
    db.session.commit()
    flash('Exam scheduled successfully! 📅', 'success')
    return redirect(url_for('faculty_course_detail', course_id=exam.course_id))

@app.route('/faculty/submissions/<int:assignment_id>')
@login_required
def faculty_submissions(assignment_id):
    if current_user.role != 'faculty': return redirect(url_for('index'))
    assignment = Assignment.query.get_or_404(assignment_id)
    submissions = db.session.query(Submission, User)\
        .join(User, Submission.student_id == User.id)\
        .filter(Submission.assignment_id == assignment_id).all()
    return render_template('faculty/submissions.html', assignment=assignment, submissions=submissions)

@app.route('/faculty/grade/<int:submission_id>', methods=['POST'])
@login_required
def faculty_grade_submission(submission_id):
    if current_user.role != 'faculty': return redirect(url_for('index'))
    submission = Submission.query.get_or_404(submission_id)
    submission.grade = float(request.form.get('grade', 0))
    submission.feedback = request.form.get('feedback', '')
    db.session.commit()
    flash('Grade submitted! ✅', 'success')
    return redirect(url_for('faculty_submissions', assignment_id=submission.assignment_id))

@app.route('/faculty/results/<int:exam_id>')
@login_required
def faculty_results(exam_id):
    if current_user.role != 'faculty': return redirect(url_for('index'))
    exam = Exam.query.get_or_404(exam_id)
    students = db.session.query(User, Enrollment)\
        .join(Enrollment, User.id == Enrollment.student_id)\
        .filter(Enrollment.course_id == exam.course_id, Enrollment.status == 'approved').all()
    results = {r.student_id: r for r in Result.query.filter_by(exam_id=exam_id).all()}
    return render_template('faculty/results.html', exam=exam, students=students, results=results)

@app.route('/faculty/results/save', methods=['POST'])
@login_required
def faculty_save_results():
    if current_user.role != 'faculty': return redirect(url_for('index'))
    exam_id = int(request.form.get('exam_id'))
    exam = Exam.query.get_or_404(exam_id)
    student_ids = request.form.getlist('student_id[]')
    marks_list = request.form.getlist('marks[]')

    for sid, marks in zip(student_ids, marks_list):
        if marks:
            marks_val = float(marks)
            pct = (marks_val / exam.max_marks) * 100
            grade = get_grade_letter(pct)
            existing = Result.query.filter_by(exam_id=exam_id, student_id=sid).first()
            if existing:
                existing.marks_obtained = marks_val
                existing.grade_letter = grade
            else:
                result = Result(exam_id=exam_id, student_id=int(sid),
                               marks_obtained=marks_val, total_marks=exam.max_marks,
                               grade_letter=grade, published=True)
                db.session.add(result)
    db.session.commit()
    flash('Results saved and published! 🎉', 'success')
    return redirect(url_for('faculty_results', exam_id=exam_id))

# ============================================================
# STUDENT ROUTES
# ============================================================

@app.route('/student/dashboard')
@login_required
def student_dashboard():
    if current_user.role != 'student': return redirect(url_for('index'))
    enrollments = Enrollment.query.filter_by(student_id=current_user.id).all()
    approved_courses = [e for e in enrollments if e.status == 'approved']
    pending_courses = [e for e in enrollments if e.status == 'pending']

    upcoming_assignments = []
    upcoming_exams = []
    for e in approved_courses:
        course = Course.query.get(e.course_id)
        if course:
            for a in course.assignments:
                if a.due_date and a.due_date >= datetime.utcnow():
                    sub = Submission.query.filter_by(assignment_id=a.id, student_id=current_user.id).first()
                    if not sub:
                        upcoming_assignments.append({'assignment': a, 'course': course})
            for ex in course.exams:
                if ex.exam_date and ex.exam_date >= datetime.utcnow():
                    upcoming_exams.append({'exam': ex, 'course': course})

    results = db.session.query(Result, Exam, Course)\
        .join(Exam, Result.exam_id == Exam.id)\
        .join(Course, Exam.course_id == Course.id)\
        .filter(Result.student_id == current_user.id, Result.published == True)\
        .order_by(Result.created_at.desc()).limit(5).all()

    announcements = Announcement.query.filter(
        Announcement.target_role.in_(['all', 'student'])
    ).order_by(Announcement.created_at.desc()).limit(4).all()

    return render_template('student/dashboard.html',
        approved_courses=approved_courses, pending_courses=pending_courses,
        upcoming_assignments=upcoming_assignments[:5], upcoming_exams=upcoming_exams[:5],
        recent_results=results, announcements=announcements)

@app.route('/student/courses')
@login_required
def student_courses():
    if current_user.role != 'student': return redirect(url_for('index'))
    all_courses = Course.query.filter_by(is_active=True).all()
    enrolled_ids = [e.course_id for e in Enrollment.query.filter_by(student_id=current_user.id).all()]
    return render_template('student/courses.html', all_courses=all_courses, enrolled_ids=enrolled_ids)

@app.route('/student/enroll/<int:course_id>', methods=['POST'])
@login_required
def student_enroll(course_id):
    if current_user.role != 'student': return redirect(url_for('index'))
    existing = Enrollment.query.filter_by(student_id=current_user.id, course_id=course_id).first()
    if existing:
        flash('You are already enrolled or have a pending request for this course.', 'warning')
        return redirect(url_for('student_courses'))
    enrollment = Enrollment(student_id=current_user.id, course_id=course_id)
    db.session.add(enrollment)
    db.session.commit()
    flash('Enrollment request submitted! Awaiting admin approval. ⏳', 'success')
    return redirect(url_for('student_courses'))

@app.route('/student/my-courses')
@login_required
def student_my_courses():
    if current_user.role != 'student': return redirect(url_for('index'))
    enrollments = db.session.query(Enrollment, Course)\
        .join(Course, Enrollment.course_id == Course.id)\
        .filter(Enrollment.student_id == current_user.id, Enrollment.status == 'approved').all()
    return render_template('student/my_courses.html', enrollments=enrollments)

@app.route('/student/courses/<int:course_id>')
@login_required
def student_course_detail(course_id):
    if current_user.role != 'student': return redirect(url_for('index'))
    enrollment = Enrollment.query.filter_by(
        student_id=current_user.id, course_id=course_id, status='approved').first()
    if not enrollment:
        flash('You are not enrolled in this course.', 'danger')
        return redirect(url_for('student_courses'))
    course = Course.query.get_or_404(course_id)
    assignments = Assignment.query.filter_by(course_id=course_id).all()
    materials = Material.query.filter_by(course_id=course_id).all()
    exams = Exam.query.filter_by(course_id=course_id).all()
    my_submissions = {s.assignment_id: s for s in Submission.query.filter_by(student_id=current_user.id).all()}
    my_results = {r.exam_id: r for r in Result.query.filter_by(student_id=current_user.id, published=True).all()}
    return render_template('student/course_detail.html',
        course=course, assignments=assignments, materials=materials, exams=exams,
        my_submissions=my_submissions, my_results=my_results)

@app.route('/student/submit/<int:assignment_id>', methods=['POST'])
@login_required
def student_submit_assignment(assignment_id):
    if current_user.role != 'student': return redirect(url_for('index'))
    assignment = Assignment.query.get_or_404(assignment_id)
    existing = Submission.query.filter_by(assignment_id=assignment_id, student_id=current_user.id).first()
    if existing:
        flash('You have already submitted this assignment.', 'warning')
        return redirect(url_for('student_course_detail', course_id=assignment.course_id))

    file_path = None
    if 'file' in request.files and request.files['file'].filename:
        f = request.files['file']
        if allowed_file(f.filename):
            filename = f'{current_user.id}_{assignment_id}_{secure_filename(f.filename)}'
            f.save(os.path.join('uploads/submissions', filename))
            file_path = filename

    is_late = False
    if assignment.due_date and datetime.utcnow() > assignment.due_date:
        is_late = True

    submission = Submission(
        assignment_id=assignment_id,
        student_id=current_user.id,
        file_path=file_path,
        is_late=is_late
    )
    db.session.add(submission)
    db.session.commit()
    if is_late:
        flash('Assignment submitted (late submission noted). ⚠️', 'warning')
    else:
        flash('Assignment submitted successfully! ✅', 'success')
    return redirect(url_for('student_course_detail', course_id=assignment.course_id))

@app.route('/student/results')
@login_required
def student_results():
    if current_user.role != 'student': return redirect(url_for('index'))
    results = db.session.query(Result, Exam, Course)\
        .join(Exam, Result.exam_id == Exam.id)\
        .join(Course, Exam.course_id == Course.id)\
        .filter(Result.student_id == current_user.id, Result.published == True)\
        .order_by(Result.created_at.desc()).all()
    return render_template('student/results.html', results=results)

@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    if request.method == 'POST':
        current_user.name = request.form.get('name', current_user.name)
        current_user.phone = request.form.get('phone', current_user.phone)
        current_user.department = request.form.get('department', current_user.department)
        if request.form.get('new_password'):
            current_user.password = generate_password_hash(request.form.get('new_password'))
        db.session.commit()
        flash('Profile updated successfully! ✅', 'success')
    return render_template('profile.html')

# ============================================================
# API ROUTES (JSON)
# ============================================================

@app.route('/api/stats')
@login_required
def api_stats():
    return jsonify({
        'total_students': User.query.filter_by(role='student').count(),
        'total_faculty': User.query.filter_by(role='faculty').count(),
        'total_courses': Course.query.count(),
        'pending_enrollments': Enrollment.query.filter_by(status='pending').count()
    })

# ============================================================
# DATABASE SEEDING
# ============================================================

def seed_database():
    if User.query.count() > 0:
        return

    # Create admin
    admin = User(name='Admin User', email='admin@cms.edu',
                 password=generate_password_hash('admin123'),
                 role='admin', department='Administration', phone='9876543210')
    db.session.add(admin)

    # Create faculty
    faculty1 = User(name='Dr. Rajesh Kumar', email='faculty@cms.edu',
                    password=generate_password_hash('faculty123'),
                    role='faculty', department='Computer Science', phone='9876543211')
    faculty2 = User(name='Prof. Priya Sharma', email='priya@cms.edu',
                    password=generate_password_hash('faculty123'),
                    role='faculty', department='Mathematics', phone='9876543212')
    db.session.add_all([faculty1, faculty2])

    # Create students
    students = [
        User(name='Arun Krishnan', email='student@cms.edu', password=generate_password_hash('student123'),
             role='student', department='Computer Science', phone='9876543213'),
        User(name='Kavitha Rajan', email='kavitha@cms.edu', password=generate_password_hash('student123'),
             role='student', department='Mathematics', phone='9876543214'),
        User(name='Vignesh Murugan', email='vignesh@cms.edu', password=generate_password_hash('student123'),
             role='student', department='Computer Science', phone='9876543215'),
    ]
    db.session.add_all(students)
    db.session.commit()

    # Create courses
    courses = [
        Course(name='Data Structures & Algorithms', code='CS201', credits=4,
               semester=3, department='Computer Science', faculty_id=faculty1.id,
               description='Learn fundamental data structures and algorithmic thinking.', max_students=60),
        Course(name='Database Management Systems', code='CS301', credits=3,
               semester=5, department='Computer Science', faculty_id=faculty1.id,
               description='Relational databases, SQL, and database design principles.', max_students=55),
        Course(name='Calculus & Linear Algebra', code='MA101', credits=4,
               semester=1, department='Mathematics', faculty_id=faculty2.id,
               description='Foundation mathematics for engineering students.', max_students=70),
        Course(name='Machine Learning Fundamentals', code='CS401', credits=3,
               semester=7, department='Computer Science', faculty_id=faculty1.id,
               description='Introduction to ML algorithms and applications.', max_students=45),
        Course(name='Web Technologies', code='CS302', credits=3,
               semester=5, department='Computer Science', faculty_id=faculty1.id,
               description='HTML, CSS, JavaScript, and modern web frameworks.', max_students=50),
    ]
    db.session.add_all(courses)
    db.session.commit()

    # Create enrollments
    enrollments = [
        Enrollment(student_id=students[0].id, course_id=courses[0].id, status='approved', approved_at=datetime.utcnow()),
        Enrollment(student_id=students[0].id, course_id=courses[1].id, status='approved', approved_at=datetime.utcnow()),
        Enrollment(student_id=students[0].id, course_id=courses[4].id, status='pending'),
        Enrollment(student_id=students[1].id, course_id=courses[2].id, status='approved', approved_at=datetime.utcnow()),
        Enrollment(student_id=students[2].id, course_id=courses[0].id, status='approved', approved_at=datetime.utcnow()),
        Enrollment(student_id=students[2].id, course_id=courses[3].id, status='pending'),
    ]
    db.session.add_all(enrollments)

    # Create assignments
    assignments = [
        Assignment(course_id=courses[0].id, title='Binary Search Tree Implementation',
                   description='Implement BST with insert, delete, and search operations.',
                   due_date=datetime(2024, 4, 15, 23, 59), max_marks=100),
        Assignment(course_id=courses[1].id, title='ER Diagram Design',
                   description='Design a comprehensive ER diagram for a library management system.',
                   due_date=datetime(2024, 4, 20, 23, 59), max_marks=50),
        Assignment(course_id=courses[3].id, title='Linear Regression Project',
                   description='Implement linear regression from scratch using Python.',
                   due_date=datetime(2024, 4, 25, 23, 59), max_marks=100),
    ]
    db.session.add_all(assignments)

    # Create exams
    exams = [
        Exam(course_id=courses[0].id, title='DSA Mid-Term Exam', exam_type='midterm',
             exam_date=datetime(2024, 4, 10, 9, 0), duration=180, max_marks=100, venue='Hall A'),
        Exam(course_id=courses[1].id, title='DBMS Final Exam', exam_type='final',
             exam_date=datetime(2024, 5, 5, 10, 0), duration=180, max_marks=100, venue='Hall B'),
    ]
    db.session.add_all(exams)

    # Create announcement
    ann = Announcement(title='Welcome to CMS Academic Portal!',
                       content='Welcome to the Course Management System. All students please check your enrolled courses and upcoming assignments.',
                       author_id=admin.id, target_role='all')
    db.session.add(ann)

    db.session.commit()
    print("✅ Database seeded with sample data!")
    print("📧 Login credentials:")
    print("   Admin:   admin@cms.edu / admin123")
    print("   Faculty: faculty@cms.edu / faculty123")
    print("   Student: student@cms.edu / student123")

with app.app_context():
    db.create_all()
    seed_database()

if __name__ == '__main__':
    print("\n🎓 Course Management System Starting...")
    print("🌐 Open: http://localhost:5000")
    print("─" * 50)
    app.run(debug=True, host='0.0.0.0', port=5000)
