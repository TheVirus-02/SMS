from .attendance import urlpatterns as attendance_urlpatterns
from .automation import urlpatterns as automation_urlpatterns
from .batches import urlpatterns as batch_urlpatterns
from .counsellors import urlpatterns as counsellor_urlpatterns
from .courses import urlpatterns as course_urlpatterns
from .dashboard import urlpatterns as dashboard_urlpatterns
from .enquiries import urlpatterns as enquiry_urlpatterns
from .exams import urlpatterns as exam_urlpatterns
from .installments import urlpatterns as installment_urlpatterns
from .logistics import urlpatterns as logistics_urlpatterns
from .portal import urlpatterns as portal_urlpatterns
from .students import urlpatterns as student_urlpatterns
from .trainers import urlpatterns as trainer_urlpatterns

urlpatterns = (
    portal_urlpatterns
    + dashboard_urlpatterns
    + batch_urlpatterns
    + counsellor_urlpatterns
    + course_urlpatterns
    + enquiry_urlpatterns
    + student_urlpatterns
    + installment_urlpatterns
    + trainer_urlpatterns
    + attendance_urlpatterns
    + automation_urlpatterns
    + logistics_urlpatterns
    + exam_urlpatterns
)
