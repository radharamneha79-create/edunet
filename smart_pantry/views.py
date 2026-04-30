from datetime import date, timedelta

from django import forms
from django.conf import settings
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.models import User
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.views.decorators.http import require_POST
from django.views.generic import ListView
from twilio.rest import Client

from .forms import OTPLoginForm, OTPVerifyForm, ProfileForm, RegisterForm
from .models import PantryItem, UserProfile


class QuickAddForm(forms.ModelForm):
    class Meta:
        model = PantryItem
        fields = ["name", "category", "quantity", "unit", "expiration_date", "expiration_time", "image", "qr_code_data"]
        widgets = {
            "expiration_date": forms.DateInput(attrs={"type": "date", "class": "form-control"}),
            "expiration_time": forms.TimeInput(attrs={"type": "time", "class": "form-control"}),
            "name": forms.TextInput(attrs={"class": "form-control", "placeholder": "Milk, Apples, Eggs..."}),
            "quantity": forms.NumberInput(attrs={"class": "form-control", "step": "0.1"}),
            "category": forms.Select(attrs={"class": "form-select"}),
            "unit": forms.Select(attrs={"class": "form-select"}),
            "image": forms.ClearableFileInput(attrs={"class": "form-control", "accept": "image/*", "capture": "environment"}),
            "qr_code_data": forms.HiddenInput(),
        }


class PantryDashboardView(LoginRequiredMixin, ListView):
    model = PantryItem
    template_name = "smart_pantry/dashboard.html"
    context_object_name = "items"
    login_url = reverse_lazy("smart_pantry:login")

    def get_queryset(self):
        queryset = PantryItem.objects.filter(user=self.request.user)
        query = self.request.GET.get("q", "").strip()
        if query:
            queryset = queryset.filter(
                Q(name__icontains=query) | Q(category__icontains=query)
            )
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        today = date.today()
        items = context["items"]

        expired_items = items.filter(expiration_date__lt=today)
        expiring_soon_items = items.filter(expiration_date__gte=today, expiration_date__lte=today + timedelta(days=5))
        good_to_go_items = items.filter(expiration_date__gt=today + timedelta(days=5))

        context.update(
            expired_items=expired_items,
            expiring_soon_items=expiring_soon_items,
            good_to_go_items=good_to_go_items,
            quick_add_form=kwargs.get("quick_add_form", QuickAddForm()),
            query=self.request.GET.get("q", ""),
        )
        return context

    def post(self, request, *args, **kwargs):
        # Handle item removal
        if 'remove_item' in request.POST:
            item_id = request.POST.get('item_id')
            if item_id:
                try:
                    item = get_object_or_404(PantryItem, pk=item_id, user=request.user)
                    item_name = item.name
                    item.delete()
                    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                        return JsonResponse({'success': True, 'message': f'Removed: {item_name}'})
                    return redirect(reverse("smart_pantry:dashboard"))
                except:
                    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                        return JsonResponse({'success': False, 'message': 'Item not found'})
                    return redirect(reverse("smart_pantry:dashboard"))

        # Handle item addition
        form = QuickAddForm(request.POST, request.FILES)
        if form.is_valid():
            item = form.save(commit=False)
            item.user = request.user
            item.save()
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                item = form.instance
                return JsonResponse({
                    'success': True,
                    'message': f'Added: {item.name}',
                    'item': {
                        'name': item.name,
                        'category': item.category,
                        'quantity': float(item.quantity),
                        'unit': item.unit,
                        'status': item.status,
                        'days_until_expiration': item.days_until_expiration
                    }
                })
            return redirect(reverse("smart_pantry:dashboard"))
        self.object_list = self.get_queryset()
        context = self.get_context_data(quick_add_form=form)
        return self.render_to_response(context)


def generate_otp():
    from random import randint

    return f"{randint(100000, 999999)}"

@require_POST
@login_required(login_url=reverse_lazy("smart_pantry:login"))
def ajax_remove_item(request):
    import json

    try:
        data = json.loads(request.body.decode('utf-8'))
        item_name = data.get('item_name', '').strip()
    except Exception:
        return JsonResponse({'success': False, 'message': 'Invalid request format.'}, status=400)

    if not item_name:
        return JsonResponse({'success': False, 'message': 'Item name is required.'}, status=400)

    item = PantryItem.objects.filter(user=request.user, name__iexact=item_name).first()
    if not item:
        return JsonResponse({'success': False, 'message': f'Item not found: {item_name}'}, status=404)

    item.delete()
    return JsonResponse({'success': True, 'message': f'Removed: {item_name}'})


def send_otp_sms(phone_number, body):
    account_sid = settings.TWILIO_ACCOUNT_SID
    auth_token = settings.TWILIO_AUTH_TOKEN
    from_number = settings.TWILIO_FROM_NUMBER

    if not account_sid or not auth_token or not from_number:
        raise RuntimeError("Twilio credentials are not configured.")

    client = Client(account_sid, auth_token)
    message = client.messages.create(
        body=body,
        from_=from_number,
        to=phone_number,
    )
    return message.sid


def register_view(request):
    if request.method == "POST":
        form = RegisterForm(request.POST, request.FILES)
        if form.is_valid():
            user = form.save()
            profile = UserProfile.objects.create(
                user=user,
                phone_number=form.cleaned_data.get("phone_number", ""),
                full_name=form.cleaned_data.get("full_name", ""),
                gender=form.cleaned_data.get("gender", ""),
                country=form.cleaned_data.get("country", ""),
                profile_image=form.cleaned_data.get("profile_image"),
            )
            login(request, user)
            return redirect(reverse("smart_pantry:dashboard"))
    else:
        form = RegisterForm()

    return render(request, "smart_pantry/register.html", {"form": form})


@login_required(login_url=reverse_lazy("smart_pantry:login"))
def account_view(request):
    profile = request.user.profile
    if request.method == "POST":
        form = ProfileForm(request.POST, request.FILES, instance=profile)
        if form.is_valid():
            form.save()
            return redirect(reverse("smart_pantry:account"))
    else:
        form = ProfileForm(instance=profile)
    return render(request, "smart_pantry/account.html", {"form": form, "profile": profile})


def otp_login_view(request):
    otp_sent = request.session.get("otp_sent", False)
    otp_code = request.session.get("otp_code", None)
    email = request.session.get("otp_email", "")
    phone_number = request.session.get("otp_phone", "")
    message = None

    if request.method == "POST":
        if "send_otp" in request.POST:
            form = OTPLoginForm(request.POST)
            if form.is_valid():
                email = form.cleaned_data["email"]
                phone_number = form.cleaned_data["phone_number"]
                try:
                    user = User.objects.get(email=email)
                except User.DoesNotExist:
                    user = User(username=email, email=email)
                    user.set_unusable_password()
                    user.save()
                    UserProfile.objects.create(
                        user=user,
                        phone_number=phone_number,
                        full_name="",
                        gender="",
                        country="",
                    )

                profile = getattr(user, "profile", None)
                if not profile or profile.phone_number != phone_number:
                    form.add_error(None, "Email and phone number do not match.")
                    return render(request, "registration/login.html", {"form": form, "otp_sent": False})

                otp_code = generate_otp()
                request.session["otp_code"] = otp_code
                request.session["otp_email"] = email
                request.session["otp_phone"] = phone_number
                request.session["otp_sent"] = True
                request.session.modified = True
                try:
                    send_otp_sms(phone_number, f"Your Smart Pantry login OTP is {otp_code}")
                    message = f"OTP sent to {phone_number}. Check your SMS."
                except Exception as exc:
                    message = f"SMS send failed. OTP is {otp_code} (demo mode)."
                verify_form = OTPVerifyForm()
                return render(request, "registration/login.html", {
                    "form": OTPLoginForm(initial={"email": email, "phone_number": phone_number}),
                    "verify_form": verify_form,
                    "otp_sent": True,
                    "message": message,
                })
            return render(request, "registration/login.html", {"form": form, "otp_sent": False})

        if "verify_otp" in request.POST:
            verify_form = OTPVerifyForm(request.POST)
            if verify_form.is_valid():
                otp_code_entered = verify_form.cleaned_data["otp_code"].strip()
                stored_otp = request.session.get("otp_code")
                if stored_otp and otp_code_entered == stored_otp:
                    email = request.session.get("otp_email")
                    try:
                        user = User.objects.get(email=email)
                        login(request, user)
                        request.session.pop("otp_code", None)
                        request.session.pop("otp_sent", None)
                        request.session.pop("otp_email", None)
                        request.session.pop("otp_phone", None)
                        return redirect(reverse("smart_pantry:dashboard"))
                    except User.DoesNotExist:
                        message = "User not found during login. Please try again."
                else:
                    message = "Invalid OTP code. Please try again."
            else:
                message = "Please enter a valid OTP code."
            return render(request, "registration/login.html", {
                "form": OTPLoginForm(initial={"email": email, "phone_number": phone_number}),
                "verify_form": verify_form,
                "otp_sent": True,
                "message": message,
            })

    form = OTPLoginForm(initial={"email": email, "phone_number": phone_number})
    verify_form = OTPVerifyForm()
    return render(request, "registration/login.html", {
        "form": form,
        "verify_form": verify_form,
        "otp_sent": otp_sent,
        "message": message,
    })


@login_required(login_url=reverse_lazy("smart_pantry:login"))
def home_view(request):
    """Home page with overview and quick actions."""
    user = request.user
    items = PantryItem.objects.filter(user=user)
    today = date.today()
    
    expiry_alerts = items.filter(
        expiration_date__isnull=False,
        expiration_date__lte=today + timedelta(days=7)
    ).count()
    
    total_items = items.count()
    
    context = {
        'total_items': total_items,
        'expiry_alerts': expiry_alerts,
    }
    return render(request, "smart_pantry/home.html", context)


@login_required(login_url=reverse_lazy("smart_pantry:login"))
def settings_view(request):
    """Settings page for app configuration."""
    profile = request.user.profile
    context = {
        'profile': profile,
    }
    return render(request, "smart_pantry/settings.html", context)


@login_required(login_url=reverse_lazy("smart_pantry:login"))
def dashboard_view(request):
    """Enhanced dashboard showing item statistics and actions."""
    user = request.user
    items = PantryItem.objects.filter(user=user)
    today = date.today()

    if request.method == 'POST':
        quick_add_form = QuickAddForm(request.POST, request.FILES)
        if quick_add_form.is_valid():
            item = quick_add_form.save(commit=False)
            item.user = user
            item.save()
            return redirect(reverse("smart_pantry:dashboard_new"))
    else:
        quick_add_form = QuickAddForm()

    # Calculate expiration zones
    red_zone_items = items.filter(expiration_date__lt=today + timedelta(days=2))
    amber_zone_items = items.filter(
        expiration_date__gte=today + timedelta(days=2),
        expiration_date__lte=today + timedelta(days=5)
    )
    green_zone_items = items.filter(expiration_date__gt=today + timedelta(days=5))

    categories_count = {}
    inventory_by_category = {}
    low_stock_items = []

    low_stock_thresholds = {
        'Produce': 3,
        'Dairy': 2,
        'Meat': 2,
        'Pantry': 4,
        'Frozen': 2,
        'Snacks': 3,
    }

    for item in items:
        categories_count[item.category] = categories_count.get(item.category, 0) + 1
        inventory_by_category.setdefault(item.category, []).append(item)
        threshold = low_stock_thresholds.get(item.category, 2)
        try:
            quantity_value = float(item.quantity)
        except Exception:
            quantity_value = 0
        if quantity_value <= threshold:
            low_stock_items.append(item)

    max_category_count = max(categories_count.values()) if categories_count else 1
    categories_data = [
        {
            'category': category,
            'count': count,
            'percent': min(100, int((count / max_category_count) * 100))
        }
        for category, count in sorted(categories_count.items())
    ]

    categorized_inventory = []
    for category, category_items in sorted(inventory_by_category.items()):
        total_quantity = sum(float(item.quantity) for item in category_items)
        units = sorted({item.unit for item in category_items})
        categorized_inventory.append({
            'category': category,
            'count': len(category_items),
            'total_quantity': total_quantity,
            'units': ', '.join(units),
            'items': sorted(category_items, key=lambda x: x.name),
        })

    context = {
        'total_items': items.count(),
        'low_stock_count': len(low_stock_items),
        'low_stock_items': low_stock_items,
        'low_stock_item_ids': [item.id for item in low_stock_items],
        'red_zone_count': red_zone_items.count(),
        'amber_zone_count': amber_zone_items.count(),
        'green_zone_count': green_zone_items.count(),
        'red_zone_items': red_zone_items,
        'amber_zone_items': amber_zone_items,
        'green_zone_items': green_zone_items,
        'categories_data': categories_data,
        'categorized_inventory': categorized_inventory,
        'quick_add_form': quick_add_form,
    }
    return render(request, "smart_pantry/dashboard_new.html", context)
