from scrapy import signals
from scrapy.extensions.statsmailer import StatsMailer
from scrapy.mail import MailSender
from scrapy.exceptions import NotConfigured


class ErrorStatsMailer(StatsMailer):
    '''
    Override extensions StatsMailer that sends email
    by catching spider closed signal, so that only certain
    stats are emailed and only upon given conditions
    '''

    def __init__(self, settings, stats, recipients, mail):
        self.settings = settings
        self.stats = stats
        self.mail = mail
        self.recipients = recipients
        self.MIN_ITEMS_SCRAPED = settings['STATSMAILER_MIN_ITEMS_SCRAPED']
        self.MAX_ERRORS = settings['STATSMAILER_MAX_ERRORS']

    @classmethod
    def from_crawler(cls, crawler):
        recipients = crawler.settings.getlist("STATSMAILER_RCPTS")
        if not recipients:
            raise NotConfigured
        mail = MailSender.from_settings(crawler.settings)
        ext = cls(crawler.settings, crawler.stats, recipients, mail)
        crawler.signals.connect(ext.spider_closed, signal=signals.spider_closed)
        return ext

    def spider_closed(self, spider):
        '''
        Args:
            self --- Extension instance
            spider --- Scrapy spider instance
        '''
        # Get the stats
        spider_stats = self.stats.get_stats(spider)
        items_scraped = self.stats.get_value('item_scraped_count', 0)

        # Errors
        errors_count = 0
        for key in self.stats.get_stats(spider).keys():
            if 'spider_exceptions' in key:
                errors_count += self.stats.get_value(key)

        if (items_scraped < self.MIN_ITEMS_SCRAPED or errors_count > self.MAX_ERRORS):
            # Build subject
            subject = '[Spider {}] Alert'.format(spider.name)

            # Build body (double \n\n needed it seems. Consider proper template
            # later perhaps)
            body = "Alert triggered, please check the crawl stats below:\n\n"
            body += ",\n\n".join("%-50s : %s" % i for i in spider_stats.items())

            # Send mail
            return self.mail.send(self.recipients, subject, body)


class UniqueIDStats(object):

    def __init__(self, settings, stats):
        self.settings = settings
        self.stats = stats

    @classmethod
    def from_crawler(cls, crawler):
        ext = cls(crawler.settings, crawler.stats)
        crawler.signals.connect(ext.spider_closed, signal=signals.spider_closed)
        return ext

    def spider_closed(self, spider):
        self.stats.set_value('duplicate_stockx_ids', spider.duplicate_stockx_ids)
        self.stats.set_value('unique_stockx_ids_count', len(spider.stockx_ids))
