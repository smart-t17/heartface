import csv
import arrow
from datetime import datetime

from django.conf.urls import url
from django.http import HttpResponse
from django.db.models import Sum
from django.forms.models import BaseInlineFormSet
from django.urls import path
from django.contrib import admin, postgres, messages
from django.contrib.admin import SimpleListFilter
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.html import format_html
from heartface.apps.core.models import *
from adminsortable2.admin import SortableInlineAdminMixin
from heartface.libs.scrape import update_supplierprod
from heartface.libs.scrape import ScrapingException


class VideosInLine(admin.TabularInline):
    model = Video
    extra = 0
    fields = [
        'title',
        'description',
        'view_count',
        'recommended',
        'created',
        'published',
        'cdn_available',
        'video_length'
    ]
    readonly_fields = [
        'title',
        'description',
        'view_count',
        'recommended',
        'created',
        'published',
        'cdn_available',
        'video_length'
    ]


class JoinedFilter(SimpleListFilter):
    title = 'joined'
    parameter_name = 'joined'

    LOOKUP_VALUES = {
        '24h': {'days': -1},
        '48h': {'days': -2},
        '1week': {'weeks': -1},
        '1month': {'months': -1},
        'quarter': {'months': -3},
        '6months': {'months': -6},
        '1year': {'years': -1}
    }

    def lookups(self, request, model_admin):
        return [('24h', '24h'), ('48h', '48h'), ('1week', '1 week'), ('1month', '1 month'), ('quarter', 'quarter'),
                ('6months', '6 months'), ('1year', '1 year')]

    def queryset(self, request, queryset):
        now = arrow.utcnow()
        return queryset.filter(date_joined__gt=now.shift(**self.LOOKUP_VALUES[self.value()]).datetime) if self.value() else queryset


class FirstVideoListFilter(SimpleListFilter):
    title = 'first'
    parameter_name = 'first'

    def lookups(self, request, model_admin):
        return [('yes', 'yes')]

    def queryset(self, request, queryset):
        return queryset.order_by('owner', 'created').distinct('owner') if self.value() == 'yes' else queryset


class UserAdmin(admin.ModelAdmin):
    list_display = [
        'id',
        'full_name',
        'username',
        # 'date_joined',
        'number_of_followers',
        'number_of_videos_uploaded',
    ]

    list_display_links = ['id', 'full_name', 'username']
    search_fields = ['full_name', 'username', 'email', ]
    list_filter = [JoinedFilter]
    inlines = [VideosInLine]
    readonly_fields = ['profile_picture', 'number_of_followings', 'number_of_followers', 'like_count', 'number_of_videos_uploaded']

    def like_count(self, obj):
        return Like.objects.filter(video__owner=obj).count()

    def number_of_followings(self, obj):
        return obj.following.all().count()

    def number_of_followers(self, obj):
        return obj.followers.all().count()

    def number_of_videos_uploaded(self, obj):
        return Video.objects.filter(owner=obj).count()

    def profile_picture(self, obj):
        return format_html('<img src="%s" />' % obj.photo.url) if obj.photo is not None else ''

    number_of_followers.admin_order_field = 'followers'

    class Meta:
        model = User


class SupplierAdmin(admin.ModelAdmin):
    list_display = [
        'id',
        'name',
        'country',
    ]
    list_display_links = ['id', 'name']
    search_fields = ['name']

    fieldsets = (
        (None, {'fields': ('name', 'country', 'logo')}),
        (
            'Shipping', {
                'fields': (('shipping_cost', 'shipping_method', 'shipping_time'),
                           ('returns_cost', 'returns_method', 'return_period'),
                            'privacy_policy_url', 'terms_url', 'returns_url'),
            }
        )
    )

    class Meta:
        model = Supplier


class SupplierProductAdmin(admin.ModelAdmin):
    list_display = [
        'id',
        'supplier',
        'product',
        'price',
        'link',
        'sizes',
        'last_scraped'
    ]
    search_fields = ['supplier']

    class Meta:
        model = SupplierProduct


class ProductPictureInline(admin.StackedInline):
    model = ProductPicture


class MarketplaceURLInline(admin.StackedInline):
    model = MarketplaceURL


class CollectionsInline(admin.TabularInline):
    model = EditorialRecommendation.collections.through


class LenientArrayField(postgres.forms.array.SimpleArrayField):
    def to_python(self, value):
        if not isinstance(value, list):
            value = value.split(self.delimiter) if value else []

        return super().to_python([v.strip() for v in value])


class SupplierProductInlineFormset(BaseInlineFormSet):
    def save_new(self, form, commit=True):
        instance = super().save_new(form, commit=commit)
        try:
            logger.debug('On demand scrape for {}'.format(instance))
            update_supplierprod(instance)
        except ScrapingException as s_exc:
            logger.error(s_exc)
        return instance

    def save_existing(self, form, instance, commit=True):
        instance = super().save_existing(form, instance, commit=commit)
        try:
            logger.debug('On demand scrape for {}'.format(instance))
            update_supplierprod(instance)
        except ScrapingException as s_exc:
            logger.error(s_exc)
        return instance


class SupplierProductInline(admin.StackedInline):
    model = SupplierProduct
    fields = ['supplier', 'link', 'price', 'sizes']
    readonly_fields = ['price', 'sizes']
    extra = 0
    formset = SupplierProductInlineFormset

    formfield_overrides = {
        postgres.fields.array.ArrayField: {
            'form_class': LenientArrayField
        }
    }


class ProductAdmin(admin.ModelAdmin):
    list_filter = ['status']
    list_display = [
        'id',
        'name',
        'status',
        'description',
        'stockx_id',
        'handle',
        # 'link',
        # 'supplier',
    ]
    list_display_links = ['id', 'name']
    search_fields = ['name']
    readonly_fields = ['created', 'updated']
    fields = ['name', 'created', 'updated', 'description', 'primary_picture', 'stockx_id', 'colorway', 'style_code',
              'release_date', ]
    inlines = [ProductPictureInline, SupplierProductInline, MarketplaceURLInline]

    def handle(self, obj):
        return format_html('<a href="%s" class="button">Handle</a>' %
                           reverse('admin:core_product_handle', kwargs={'pk': str(obj.pk)}) if obj.handled_by is None else '')

    def handle_product(self, request, pk):
        # Prevent admins picking the same order: only set handling admin if
        # status is still 'queued'.
        if not Product.objects.filter(pk=pk, status=Product.STATUSES.queued).update(status=Product.STATUSES.processed,
                                                                                    handled_by=request.user):
            # If Product with this pk not queued we get here(then no update
            # has occurred either)
            if Product.objects.get(pk=pk).handled_by:
                messages.add_message(request, messages.WARNING,
                                     'This product is already being processed by %s' % Product.objects.get(pk=pk).handled_by.email)
            else:
                # Status isn't queued but not being handled, so handle it.
                Product.objects.filter(pk=pk).update(handled_by=request.user, status=Product.STATUSES.processed)
                messages.add_message(request, messages.WARNING,
                                     'This product was unhandled but has status other than "queued". You are now the handler.')
                return redirect('admin:core_product_change', object_id=pk)

            return redirect('admin:core_product_changelist')
        return redirect('admin:core_product_change', object_id=pk)

    def get_urls(self):
        handle_product_urls = []
        urls = super().get_urls()
        handle_product_urls.append(url(r'^(?P<pk>\d+)/handle/$', self.admin_site.admin_view(self.handle_product), name='core_product_handle'))
        return handle_product_urls + urls

    class Meta:
        model = Product


class HashtagAdmin(admin.ModelAdmin):
    list_display = [
        'id',
        'name',
    ]
    list_display_links = ['id', 'name']
    search_fields = ['name']

    class Meta:
        model = Hashtag


class VideoCDNStatusInline(admin.TabularInline):
    can_delete = False
    model = VideoCDNStatus
    readonly_fields = ['filename', 'status', 'description', 'timestamp']
    ordering = ['-timestamp']

    def has_add_permission(self, request):
        return False


class VideoAdmin(admin.ModelAdmin):
    list_display = [
        'id',
        'title',
        'owner_name',
        'created',
        'published',
        'cdn_available',
        'number_of_likes',
        'view_count',
        'number_of_reports',
        'video_content',
        'recommended',
    ]

    fieldsets = (
        (
            None, {
                'fields': ('id', 'video_content', 'videofile', 'title', 'description', 'owner', 'recommended',
                           'created', 'published', 'cdn_available', 'products', 'hashtags')
            }
        ),
        (
            'Stats', {
                'fields': (('view_count', 'number_of_likes', 'number_of_reports',
                            'upload_session_length', 'video_length'),)
            }
        )
    )

    readonly_fields = [
        'id',
        'view_count',
        'number_of_likes',
        'number_of_reports',
        'video_length',
        'upload_session_length',
        'video_content',
        'created',
        'published',
        'cdn_available',
        'hashtags',
    ]

    def date_of_upload(self, obj):
        return obj.published

    def view_count(self, obj):
        return obj.view_count

    def recommended(self, obj):
        return obj.recommended

    def upload_session_length(self, obj):
        if obj.cdn_available and obj.published:
            return '%.2f hours' % ((obj.cdn_available-obj.published).seconds/3600)

    list_display_links = ['id', 'title']
    search_fields = ['id', 'title', 'owner__username']
    list_filter = ['published', FirstVideoListFilter]
    view_count.admin_order_field = 'view_count'
    date_of_upload.admin_order_field = 'published'
    recommended.admin_order_field = 'recommended'
    filter_horizontal = ['products']

    def owner_name(self, obj):
        return format_html('<a href="%s">%s</a>' % (
        reverse('admin:core_user_change', kwargs={'object_id': str(obj.owner.pk)}), obj.owner.username))

    def number_of_likes(self, obj):
        return obj.likes.count()

    def number_of_reports(self, obj):
        return ReportedVideo.objects.filter(video=obj).count()

    def video_content(self, obj):
        if obj.cdn_available:
            src, poster = obj.videofile_cdn_url, obj.cover_picture_cdn_url
        else:
            src, poster = obj.videofile.url, ''
        return format_html('<video src="{src}" width="320" height="240" controls poster="{poster}"></video>'.format(
            src=src, poster=poster))

    class Meta:
        model = Video

    inlines = [
        VideoCDNStatusInline,
    ]


class ReportedVideoAdmin(admin.ModelAdmin):
    list_display = [
        'id',
        'video_detail',
        'uploading_user',
        'date_of_upload',
        'link_to_reporting_user',
        'reviewed',
        'date_of_report',
    ]
    search_fields = ['video']
    list_filter = ['reviewed']
    ordering = ['reviewed', '-created', ]

    def uploading_user(self, obj):
        return format_html('<a href="%s">%s</a>' % (
        reverse('admin:core_user_change', kwargs={'object_id': str(obj.video.owner.pk)}), obj.video.owner.username))

    def link_to_reporting_user(self, obj):
        if obj.reporting_user is None:
            return 'guest'
        return format_html('<a href="%s">%s</a>' % (
        reverse('admin:core_user_change', kwargs={'object_id': str(obj.reporting_user.pk)}),
        obj.reporting_user.username))

    def date_of_upload(self, obj):
        return obj.video.created

    def date_of_report(self, obj):
        return obj.created

    def video_detail(self, obj):
        return format_html('<a href="%s">%s</a>' % (
        reverse('admin:core_video_change', kwargs={'object_id': str(obj.video.pk)}), obj.video.title))

    date_of_upload.admin_order_field = 'video__created'
    date_of_report.admin_order_field = 'created'

    class Meta:
        model = ReportedVideo


class CollectionAdmin(admin.ModelAdmin):
    list_display = [
        'id',
        'name',
        'description',
        'cover_photo',
    ]
    list_display_links = ['id', 'name']
    search_fields = ['name']
    filter_horizontal = ['videos']

    class Meta:
        model = Collection


class EditorialRecommendationAdmin(admin.ModelAdmin):
    list_display = [
        'id',
        'featured_video_detail',
        'collection_list',
    ]
    search_fields = ['featured_video', ]
    inlines = [CollectionsInline, ]
    exclude = ['collections', ]
    readonly_fields = ['video_content']

    # raw_id_fields = ['featured_video']
    autocomplete_fields = ['featured_video']

    def update_selected_recommendation_featured_video(self, request, queryset):
        video_id = int(request.POST['change_video_id'])
        queryset.update(featured_video=video_id)
        messages.success(request, 'Featured video updated.')

    def featured_video_detail(self, obj):
        return format_html('<a href="%s">%s</a>' % (reverse('admin:core_video_change', kwargs={'object_id': str(obj.featured_video.pk)}), obj.featured_video.title))

    def video_content(self, obj):
        return format_html('<video src="%s" width="320" height="240" controls poster = "%s"></video>' % (
            obj.featured_video.videofile_cdn_url, obj.featured_video.cover_picture_cdn_url))

    def collection_list(self, obj):
        return "\n".join([p.name for p in obj.collections.all()])

    class Meta:
        model = EditorialRecommendation


class HomepageContentAdmin(admin.ModelAdmin):
    list_display = [
        'id',
        'created',
    ]
    readonly_fields = ['created', ]
    filter_horizontal = ['videos', 'profiles']

    class Meta:
        model = HomepageContent


class OrderAdmin(admin.ModelAdmin):
    list_display = [
        'id',
        'product_name',
        'product_url',
        'country',
        'status',
        'handle',
    ]
    autocomplete_fields = ['product', ]
    list_display_links = ['id']
    search_fields = ['customer_name']
    readonly_fields = [
        'customer_name',
        'address',
        'phone',
        'video_url',
        'video_owner',
        'country',
        'product_url',
        'item_total_cost',
        'shipping_cost',
        'total_commission_earned',
        'stripe_payment_confirmation_code',
        'size',
        'referral_url'
    ]
    list_filter = ['status']

    def get_fieldsets(self, request, obj=None):
        if obj is not None and obj.status == Order.STATUSES.processing:
            return (
                    ('Order info', {
                        'fields': ('handled_by', 'retailer_order_id', 'referral_url', 'customer_name',
                                   'address', 'phone', 'stripe_payment_confirmation_code')
                    }), ('Product info', {
                        'fields': ('customer', 'status', 'country', 'product_url', 'video_owner', 'video_url',
                                   'size', 'item_total_cost', 'shipping_cost', 'total_commission_earned')
                    })
                )

        return (
            (None, {
                'fields': ('retailer_order_id', 'customer', 'product', 'video', 'status', 'item_total_cost', 'shipping_cost', 'total_commission_earned',
                           'stripe_payment_confirmation_code', 'referral_url', 'product_url', 'size', 'video_owner', 'video_url')
            })
        ,)

    def referral_url(self, obj):
        # Order.product is a SupplierProduct
        ref_url = settings.SKIMLINKS_AFFILIATE_URL_TEMPLATE % (settings.SKIMLINKS_SITE_ID, obj.product.link or '', obj.pk)

        return format_html('<a href="%s">%s</a>' % (ref_url, ref_url))

    def stripe_payment_confirmation_code(self, obj):
        return ''

    def shipping_cost(self, obj):
        return ''

    def total_commission_earned(self, obj):
        return obj.commission_earned or ''

    def item_total_cost(self, obj):
        return obj.product.price or ''

    def video_owner(self, obj):
        return obj.video.owner.username if obj.video else ''

    def video_url(self, obj):
        return format_html('<a href="%s">%s</a>' %
                           (reverse('admin:core_video_change', kwargs={'object_id': str(obj.video.pk)}), obj.video.title)
                           if obj.video is not None else ''
                           )

    def product_name(self, obj):
        return obj.product.product.name

    def country(self, obj):
        # obj.product is actually a SupplierProduct instance
        return obj.product.supplier.country

    def product_url(self, obj):
        # Order.product is a SupplierProduct
        prod_url = obj.product.link if obj.product.link is not None else ''
        return format_html('<a href="%s">%s</a>' % (prod_url, prod_url))

    def customer_name(self, obj):
        hlink = reverse('admin:core_user_change', kwargs={'object_id': str(obj.customer.pk)})
        htext = "%s (via Heartface)" % obj.customer.full_name
        return format_html('<a href="%s">%s</a>' % (hlink, htext))

    def address(self, obj):
        return str(obj.customer.address)

    def phone(self, obj):
        return str(obj.customer.phone)

    def handle(self, obj):
        return format_html('<a href="%s" class="button">Handle</a>' %
                           reverse('admin:core_order_handle', kwargs={'pk': str(obj.pk)}) if obj.handled_by is None else '')

    def get_readonly_fields(self, request, obj=None):
        ro_fields = super().get_readonly_fields(request, obj)
        return ro_fields if obj and obj.status == Order.STATUSES.processing else ro_fields + ['retailer_order_id']

    def get_urls(self):
        handle_order_urls = []
        urls = super().get_urls()
        handle_order_urls.append(url(r'^(?P<pk>\d+)/handle/$', self.admin_site.admin_view(self.handle_order), name='core_order_handle'))
        return handle_order_urls + urls

    def change_view(self, request, object_id, form_url='', extra_context=None):  # (self, request, pk):
        order = Order.objects.get(pk=object_id)
        if order.status != Order.STATUSES.new and request.user != order.handled_by:
            if order.handled_by is not None:
                messages.add_message(request, messages.WARNING, 'This order is already being processed by %s' % order.handled_by.email)
            else:
                messages.add_message(request, messages.WARNING, 'This order is not being handled by anyone')
        return super().change_view(request, object_id, form_url, extra_context)

    def handle_order(self, request, pk):
        # Prevent admins picking the same order: only set handling admin if status is still 'new'.
        if not Order.objects.filter(pk=pk, status=Order.STATUSES.new).update(status=Order.STATUSES.processing,
                                                                             handled_by=request.user):
            # Can also get here if unhandled but status is not 'new' (although
            # shouldn't happen in practice)
            if Order.objects.get(pk=pk).handled_by:
                messages.add_message(request, messages.WARNING,
                                     'This order is already being processed by %s' % Order.objects.get(pk=pk).handled_by.email)
            else:
                # Status isn't new but not being handled, so handle it.
                Order.objects.filter(pk=pk).update(handled_by=request.user)
                messages.add_message(request, messages.WARNING,
                                     'This order was unhandled but has status other than "new". You are now the handler.')
                return redirect('admin:core_order_change', object_id=pk)

            return redirect('admin:core_order_changelist')
        return redirect('admin:core_order_change', object_id=pk)

    def render_change_form(self, request, context, *args, **kwargs):
        """
        When handled_by is in the fields (processing orders). Limit to staff
        """
        try:
            context['adminform'].form.fields['handled_by'].queryset = User.objects.filter(is_staff=True)
        except KeyError:
            pass
        return super(OrderAdmin, self).render_change_form(request, context, *args, **kwargs)

    class Meta:
        model = Order


class UserModelAdmin(admin.ModelAdmin):
    list_display = [
        'id',
        'email',
        'username',
        'full_name',
        'is_staff',
        'is_active',
    ]
    list_display_links = ['id', 'email', 'username']
    search_fields = ['email']

    class Meta:
        model = User


class LikeModelAdmin(admin.ModelAdmin):
    list_display = [
        'id',
        'video',
        'user',
        'created',
    ]
    search_fields = ['video', 'user']

    class Meta:
        model = Like


class CommentModelAdmin(admin.ModelAdmin):
    list_display = [
        'id',
        'author',
        'video',
        'text',
        'created',
    ]
    search_fields = ['author', 'video']

    class Meta:
        model = Comment


class NotificationModelAdmin(admin.ModelAdmin):
    list_display = [
        'id',
        'recipient',
        'message',
        'read',
        'timestamp',
    ]
    search_fields = ['recipient', ]

    class Meta:
        model = Notification


class FollowRecommendationsInline(SortableInlineAdminMixin, admin.TabularInline):
    model = DefaultFollowRecommendation.users.through
    autocomplete_fields = ['user']


class DefaultFollowRecommendationAdmin(admin.ModelAdmin):
    inlines = [FollowRecommendationsInline, ]
    readonly_fields = ['created', ]
    ordering = ('-created', )

    class Meta:
        model = DefaultFollowRecommendation


class MarketplaceAdmin(admin.ModelAdmin):
    list_display = [
        'id',
        'name',
    ]
    list_display_links = ['id', 'name']
    search_fields = ['name']

    class Meta:
        model = Marketplace


class ProxyAdmin(admin.ModelAdmin):
    class Meta:
        model = Proxy


class AdminAnalyticAdmin(VideoAdmin):

    change_list_template = 'admin/admin_analytics.html'

    def get_urls(self):
        urls = super().get_urls()
        my_urls = [
            path('export-csv/', self.export_csv),
        ]
        return my_urls + urls

    def get_context(self, date_range):
        queryset = self.model.objects.all()
        if date_range:
            date_format = '%d/%m/%Y'
            date_time = date_range.split('-')
            start_date = datetime.strptime(date_time[0].strip(), date_format)
            end_date = datetime.strptime(date_time[1].strip(), date_format)
            queryset = self.model.objects.filter(created__range=[start_date, end_date])

        extra_context = {
            'date_range': date_range,
            'registered_users': User.objects.count(),
            'total_video': queryset.count(),
            'video_creators': [user['owner__full_name'] for user in queryset.values('owner__full_name').distinct()],
            'total_views': queryset.aggregate(Sum('view_count'))['view_count__sum'] or 0,
            'long_video': queryset.filter(video_length__gt=settings.LONG_VIDEO_DURATION_SECONDS).count(),
            'medium_video': queryset.filter(video_length__gte=settings.SHORT_VIDEO_DURATION_SECONDS,
                                            video_length__lte=settings.LONG_VIDEO_DURATION_SECONDS).count(),
            'short_video': queryset.filter(video_length__lt=settings.SHORT_VIDEO_DURATION_SECONDS).count(),
        }

        return extra_context

    def changelist_view(self, request, extra_context=None):
        date_range = request.POST.get('daterange', '')
        extra_context = self.get_context(date_range)
        return super(AdminAnalyticAdmin, self).changelist_view(request, extra_context)

    def export_csv(self, request):
        date_range = request.GET.get('date_range', '')
        data = self.get_context(date_range)
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename={}.csv'.format('admin_analytics')
        writer = csv.writer(response)
        for key, value in data.items():
            writer.writerow([key, value])
        return response


class MissingProductAdmin(admin.ModelAdmin):
    list_display = ['id', 'name', 'color', 'user', 'video_info', 'created', 'handle']
    list_display_links = ['id', 'name']
    search_fields = ['name', 'video__title', 'user__username']
    ordering = ('-created', )

    def video_info(self, obj):
        video = obj.video
        admin_video_url = reverse('admin:core_video_change', kwargs={'object_id': video.pk})
        return format_html('<a href="%s">%s (ID: %s)</a>' % (admin_video_url, video.title, video.pk))

    video_info.short_description = "Video"

    def handle(self, obj):
        if obj.handled_by is None:
            return format_html('<a href="%s" class="button">Handle</a>' %
                               reverse('admin:missing_product_handle', kwargs={'pk': obj.pk}))
        return format_html('Handled by %s' % obj.handled_by)

    def get_urls(self):
        urls = super().get_urls()
        handle_missing_product_urls = [url(r'^(?P<pk>\d+)/handle/$', self.admin_site.admin_view(
            self.handle_missing_products), name='missing_product_handle')]
        return handle_missing_product_urls + urls

    def handle_missing_products(self, request, pk):
        if MissingProduct.objects.filter(pk=pk, handled_by=None).update(handled_by=request.user):
            messages.add_message(request, messages.WARNING,
                                 'This missing product was unhandled. Now you are the handler.')
            return redirect('admin:core_missingproduct_change', object_id=pk)
        # Avoid race condition in case other admin already handled this before
        messages.add_message(request, messages.WARNING,
                             'This missing product was already being handled.')
        return redirect('admin:core_missingproduct_changelist')

    class Meta:
        model = MissingProduct


admin.site.register(MissingProduct, MissingProductAdmin)
admin.site.register(AdminAnalytic, AdminAnalyticAdmin)
admin.site.register(Proxy, ProxyAdmin)
admin.site.register(SupplierProduct, SupplierProductAdmin)
admin.site.register(Notification, NotificationModelAdmin)
admin.site.register(Comment, CommentModelAdmin)
admin.site.register(Like, LikeModelAdmin)
admin.site.register(User, UserAdmin)
admin.site.register(Supplier, SupplierAdmin)
admin.site.register(Marketplace, MarketplaceAdmin)
admin.site.register(Product, ProductAdmin)
admin.site.register(Hashtag, HashtagAdmin)
admin.site.register(Video, VideoAdmin)
admin.site.register(ReportedVideo, ReportedVideoAdmin)
# NOTE: not used anymore. Model needs to be removed as well.
# admin.site.register(FeaturedVideo, FeaturedVideoAdmin)
admin.site.register(EditorialRecommendation, EditorialRecommendationAdmin)
admin.site.register(HomepageContent, HomepageContentAdmin)
admin.site.register(Collection, CollectionAdmin)
admin.site.register(Order, OrderAdmin)
admin.site.register(DefaultFollowRecommendation, DefaultFollowRecommendationAdmin)
