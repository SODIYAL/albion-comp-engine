-- The join code's setting is read once per statement, not once per row
-- (Supabase lint 0003 on the insert policy: a bare current_setting() is
-- re-evaluated for every row, the (select ...) form once). The rule the
-- policies already follow for auth.uid(); tests/test_supabase_schema.py
-- DB3 now pins it for current_setting() too.

alter policy "Creators seat themselves as admin" on public.guild_members
  with check (
    user_id = (select auth.uid())
    and ((role = 'admin'
          and private.guild_role_of(guild_id) is null
          and (select g.created_by from public.guilds g where g.id = guild_id) = (select auth.uid()))
         or (role = 'member'
             and guild_id = private.guild_id_for_code((select current_setting('app.join_code', true))))));
