from rest_framework.exceptions import ValidationError
from rest_framework.pagination import PageNumberPagination


class ListingPagination(PageNumberPagination):
    """Page-number pagination with a client-controlled (but capped) page size."""

    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100
    page_query_param = "page"

    def get_page_size(self, request):
        """Reject a nonsense page_size instead of silently falling back.

        Stock DRF swallows bad values, which makes `?page_size=abc` look like it
        worked. A 400 with the usual error envelope is easier to debug.
        """
        raw = request.query_params.get(self.page_size_query_param)
        if raw is None or raw == "":
            return self.page_size
        try:
            page_size = int(raw)
        except (TypeError, ValueError):
            page_size = 0
        if page_size < 1:
            raise ValidationError(
                {self.page_size_query_param: ["Must be a positive integer."]}
            )
        return min(page_size, self.max_page_size)
