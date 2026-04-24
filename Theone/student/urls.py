from .urls.attendance import urlpatterns as attendance_urlpatterns
from .urls.batches import urlpatterns as batch_urlpatterns
from .urls.counsellors import urlpatterns as counsellor_urlpatterns
from .urls.courses import urlpatterns as course_urlpatterns
from .urls.dashboard import urlpatterns as dashboard_urlpatterns
from .urls.enquiries import urlpatterns as enquiry_urlpatterns
from .urls.exams import urlpatterns as exam_urlpatterns
from .urls.installments import urlpatterns as installment_urlpatterns
from .urls.logistics import urlpatterns as logistics_urlpatterns
from .urls.students import urlpatterns as student_urlpatterns
from .urls.trainers import urlpatterns as trainer_urlpatterns

urlpatterns = (
    dashboard_urlpatterns
    + batch_urlpatterns
    + counsellor_urlpatterns
    + course_urlpatterns
    + enquiry_urlpatterns
    + student_urlpatterns
    + installment_urlpatterns
    + trainer_urlpatterns
    + attendance_urlpatterns
    + logistics_urlpatterns
    + exam_urlpatterns
)
