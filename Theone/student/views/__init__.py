from .attendance import attendance_batch_detail, attendance_batches, mark_attendance, save_attendance_record
from .batches import (
    add_batch,
    add_batch_assignment,
    batch_detail,
    batch_list,
    create_standard_batches,
    delete_batch,
    delete_batch_assignment,
    update_batch,
    update_batch_assignment,
)
from .counsellors import (
    add_counsellor,
    counsellor_detail,
    counsellor_list,
    delete_counsellor,
    update_counsellor,
)
from .courses import add_course, course_detail, course_list, delete_course, update_course
from .dashboard import index
from .enquiries import (
    add_enquiry,
    convert_enquiry,
    delete_enquiry,
    enquiry_detail,
    enquiry_list,
    today_follow_up,
    update_enquiry,
)
from .exams import certificate_dashboard, enter_marks, exam_dashboard, register_exam, toggle_certificate_status
from .logistics import logistics_dashboard, update_logistics, update_repair_pc, update_total_pc
from .students import (
    add_installment,
    batch_students,
    record,
    student_detail,
    student_registration,
    trainer_batches,
    update_student,
)
from .trainers import (
    add_schedule,
    add_trainer,
    delete_schedule,
    delete_trainer,
    trainer_schedule_page,
    trainer_detail,
    trainer_list,
    update_schedule,
    update_trainer,
)
