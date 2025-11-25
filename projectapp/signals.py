from django.contrib.auth.models import User, Group
from django.db.models.signals import post_save, post_delete, m2m_changed
from django.dispatch import receiver
from django.core.exceptions import ValidationError

from .models import Task, Milestone


# ---------------------------------------------------------
# 1. Auto-add new users to AuthenticatedUsers group
# ---------------------------------------------------------
@receiver(post_save, sender=User)
def add_user_to_authenticated_group(sender, instance, created, **kwargs):
    if created:
        group, _ = Group.objects.get_or_create(name='AuthenticatedUsers')
        instance.groups.add(group)


# ---------------------------------------------------------
# 2. M2M prerequisite validation (cycle prevention)
# ---------------------------------------------------------
@receiver(m2m_changed, sender=Task.prerequisite_tasks.through)
def check_cycle(sender, instance, action, reverse, model, pk_set, **kwargs):
    """
    Prevent circular dependencies when prerequisites are added.

    Runs on 'pre_add'. pk_set = IDs being added.
    """
    if action != 'pre_add':
        return

    # Instance must have a PK to evaluate cycles
    if instance.pk is None:
        return

    for pk in pk_set:
        try:
            prereq = model.objects.get(pk=pk)
        except model.DoesNotExist:
            continue

        if prereq.pk == instance.pk:
            raise ValidationError("A task cannot depend on itself.")

        if instance.has_cycle(prereq, instance.pk):
            raise ValidationError(
                f"Adding prerequisite '{prereq}' would create a circular dependency."
            )


# ---------------------------------------------------------
# 3. Milestone recalculation after Task deletion
# ---------------------------------------------------------
@receiver(post_delete, sender=Task)
def update_milestone_on_task_delete(sender, instance, **kwargs):
    """
    Recalculate Milestone target date when a Task is deleted.

    IMPORTANT:
        - This DOES NOT trigger on bulk deletes (QuerySet.delete())
          because Django does NOT fire signals for bulk deletions.

    Safe for:
        - Admin UI delete
        - API delete
        - `.delete()` on a Task instance
        - Inline formset deletes
    """
    if instance.milestone_id:
        try:
            ms = Milestone.objects.get(pk=instance.milestone_id)
            ms.recalculate_and_save_date()
        except Milestone.DoesNotExist:
            pass
