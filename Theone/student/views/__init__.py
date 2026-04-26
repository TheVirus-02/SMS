from .attendance import (
    attendance_batch_detail,
    attendance_batches,
    attendance_monthly_summary,
    daily_absentees,
    mark_attendance,
    save_attendance_record,
)
from .automation import (
    communication_log_list,
    daily_summary,
    reminder_center,
    send_bulk_fee_reminders,
    send_bulk_follow_up_reminders,
    send_enquiry_follow_up_reminder,
    send_fee_reminder,
    staff_center_analytics,
)
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
    export_enquiries_csv,
    today_follow_up,
    update_enquiry,
)
from .exams import certificate_dashboard, enter_marks, exam_dashboard, register_exam, toggle_certificate_status
from .logistics import logistics_dashboard, update_logistics, update_repair_pc, update_total_pc
from .students import (
    add_installment,
    admission_receipt,
    batch_students,
    delete_installment,
    daily_admissions_report,
    edit_installment,
    export_daily_admissions_csv,
    export_pending_fees_csv,
    export_student_records_csv,
    export_today_collection_csv,
    installment_receipt,
    pending_fee_list,
    record,
    reporting_dashboard,
    student_detail,
    student_registration,
    today_collection_dashboard,
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
