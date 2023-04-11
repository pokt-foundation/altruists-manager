from django.db import models
from django.contrib.auth.models import User
from django.core.validators import URLValidator
from django.core.exceptions import ValidationError

def validate_url(url:str) -> bool:
    validator = URLValidator()
    try:
        validator(url)
        return True
    except ValidationError as exception:
        raise exception

class Chain(models.Model):
    chain_id   = models.CharField(max_length=4, unique=True)
    chain_name = models.CharField(max_length=200)

    def __str__(self):
        return self.chain_id + " " + self.chain_name

class Altruist(models.Model):
    owner     = models.ForeignKey(User, on_delete=models.PROTECT, null=True)
    url       = models.CharField(max_length=200, validators=[validate_url])
    chain_id  = models.ForeignKey(Chain, on_delete=models.PROTECT)
    enabled   = models.BooleanField(default=True)

    class Meta:
        unique_together = ('chain_id', 'url',)

    def __str__(self):
        return self.chain_id.chain_id + " " + self.url


class AltruistServingLog(models.Model):
    altruist    = models.ForeignKey(Altruist, on_delete=models.CASCADE, null=True)
    chain_id    = models.CharField(max_length=4, null=True)
    # Automatically set the field to now when the object is first created.
    start_time  = models.DateTimeField(auto_now_add=True, editable = False)
    # Automatically set the field to now every time the object is saved.
    finish_time = models.DateTimeField(auto_now=True, blank=True, editable = False)

    @property
    def get_chain_id(self):
        return self.altruist.chain_id.chain_id

    @property
    def duration(self):
        return (self.finish_time - self.start_time).seconds

    def save(self, *args, **kwarg):
        self.chain_id = self.get_chain_id
        super(AltruistServingLog, self).save(*args, **kwarg)
