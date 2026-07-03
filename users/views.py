from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from django.contrib import messages
from .forms import UserUpdateForm

@login_required
def profile(request):
    if request.method == "POST":
        form = UserUpdateForm(request.POST, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, "¡Tu perfil se ha actualizado correctamente!")
            return redirect("profile")
    else:
        form = UserUpdateForm(instance=request.user)

    return render(request, "users/profile.html", {"form": form})