-- AlterTable: Add firebaseUid field to User, make passwordHash optional with default
ALTER TABLE "User" ADD COLUMN IF NOT EXISTS "firebaseUid" TEXT;
ALTER TABLE "User" ALTER COLUMN "passwordHash" SET DEFAULT '';

-- CreateIndex
CREATE UNIQUE INDEX IF NOT EXISTS "User_firebaseUid_key" ON "User"("firebaseUid");
