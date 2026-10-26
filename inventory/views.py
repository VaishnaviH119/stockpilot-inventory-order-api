from rest_framework import filters, status, viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.db.models.deletion import ProtectedError

from .models import Product
from .models import Order
from .order_serializers import OrderCreateSerializer, OrderReadSerializer
from .pagination import ProductPagination
from .permissions import IsStaffOrReadOnly
from .serializers import ProductSerializer
from .services import create_order


class ProductViewSet(viewsets.ModelViewSet):
    queryset = Product.objects.all()
    serializer_class = ProductSerializer
    permission_classes = [IsStaffOrReadOnly]
    pagination_class = ProductPagination
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["name", "sku", "description"]
    ordering_fields = ["name", "price", "stock_quantity", "created_at"]

    def destroy(self, request, *args, **kwargs):
        product = self.get_object()
        try:
            self.perform_destroy(product)
        except ProtectedError:
            return Response(
                {"detail": "A product used in an order cannot be deleted."},
                status=status.HTTP_409_CONFLICT,
            )
        return Response(status=status.HTTP_204_NO_CONTENT)


class OrderViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    http_method_names = ["get", "post", "head", "options"]

    def get_queryset(self):
        orders = Order.objects.prefetch_related("items__product")
        if self.request.user.is_staff:
            return orders
        return orders.filter(created_by=self.request.user)

    def get_serializer_class(self):
        if self.action == "create":
            return OrderCreateSerializer
        return OrderReadSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        order = create_order(user=request.user, items=serializer.validated_data["items"])
        output = OrderReadSerializer(order, context=self.get_serializer_context())
        return Response(output.data, status=status.HTTP_201_CREATED)
