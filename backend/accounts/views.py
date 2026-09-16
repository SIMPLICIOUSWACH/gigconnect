from django.core import signing
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from .email import send_verification_email
from .models import OTP, User
from .otp import issue_otp
from .serializers import RegisterSerializer, UserSerializer
from .tokens import read_email_verification_token


class RegisterView(generics.CreateAPIView):
    queryset = User.objects.all()
    serializer_class = RegisterSerializer
    permission_classes = [permissions.AllowAny]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        send_verification_email(user)
        return Response(UserSerializer(user).data, status=status.HTTP_201_CREATED)


class VerifyEmailView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request, token):
        try:
            data = read_email_verification_token(token)
        except signing.SignatureExpired:
            return Response({'detail': 'Verification link has expired.'}, status=status.HTTP_400_BAD_REQUEST)
        except signing.BadSignature:
            return Response({'detail': 'Invalid verification link.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            user = User.objects.get(id=data['user_id'])
        except User.DoesNotExist:
            return Response({'detail': 'Invalid verification link.'}, status=status.HTTP_400_BAD_REQUEST)

        user.is_email_verified = True
        user.save(update_fields=['is_email_verified'])
        return Response({'detail': 'Email verified successfully.'})


class SendOTPView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        issue_otp(request.user)
        return Response({'detail': 'OTP sent.'})


class VerifyOTPView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        code = request.data.get('code', '')
        otp = OTP.objects.filter(user=request.user, code=code, is_used=False).order_by('-created_at').first()
        if otp is None or not otp.is_valid():
            return Response({'detail': 'Invalid or expired code.'}, status=status.HTTP_400_BAD_REQUEST)

        otp.is_used = True
        otp.save(update_fields=['is_used'])
        request.user.is_phone_verified = True
        request.user.save(update_fields=['is_phone_verified'])
        return Response({'detail': 'Phone verified successfully.'})
