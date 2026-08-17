from django import forms
from .models import JobApplication

class JobApplicationForm(forms.ModelForm):
    class Meta:
        model = JobApplication
        fields = [
            "full_name",
            "email",
            "phone",
            "portfolio",
            "cover_letter",
            "cv_file",
        ]