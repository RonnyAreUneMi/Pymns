from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from .models import Profile
from django.contrib.auth.forms import AuthenticationForm

class CustomUserCreationForm(UserCreationForm):
    email = forms.EmailField(required=True, label="Correo electrónico")
    first_name = forms.CharField(max_length=30, required=True, label="Nombre")
    last_name = forms.CharField(max_length=30, required=True, label="Apellidos")
    
    class Meta:
        model = User
        fields = ("email", "first_name", "last_name", "password1", "password2")
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Remover el campo username si no lo usas
        if 'username' in self.fields:
            del self.fields['username']
    
    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data["email"]
        user.first_name = self.cleaned_data["first_name"]
        user.last_name = self.cleaned_data["last_name"]
        user.username = self.cleaned_data["email"]  # Usar email como username
        
        if commit:
            user.save()
        return user

# ← Esta clase debe estar AQUÍ, no dentro de CustomUserCreationForm
class CustomLoginForm(AuthenticationForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Cambiar la etiqueta del campo username por "Correo electrónico"
        self.fields['username'].label = "Correo electrónico"
        self.fields['username'].widget.attrs['placeholder'] = "Ingresa tu correo electrónico"
        self.fields['password'].label = "Contraseña"
        self.fields['password'].widget.attrs['placeholder'] = "Ingresa tu contraseña"